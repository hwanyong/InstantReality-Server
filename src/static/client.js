var pc = null;

function log(msg) {
    document.getElementById('logs').innerText += msg + '\n';
    console.log(msg);
}

function toggleStream() {
    var btn = document.getElementById('streamBtn');
    if (pc) {
        stop();
    } else {
        start();
    }
}

function stop() {
    var btn = document.getElementById('streamBtn');

    if (pc) {
        pc.close();
        pc = null;
    }

    // Clear Video Grid
    document.getElementById('videoGrid').innerHTML = '';

    // Reset Button UI
    btn.innerText = "Start Streaming";
    btn.className = "";
    log("Streaming stopped.");
}

function start() {
    var btn = document.getElementById('streamBtn');
    btn.disabled = true;
    btn.innerText = "Connecting...";

    var config = {
        sdpSemantics: 'unified-plan'
    };

    // Use Google's STUN server (optional for local network but good practice)
    config.iceServers = [{ urls: ['stun:stun.l.google.com:19302'] }];

    pc = new RTCPeerConnection(config);

    // Track counter to assign indices (0, 1...) to incoming streams
    var trackCounter = 0;

    // Dynamic Video Element Creation
    pc.ontrack = function (evt) {
        log("Track received: " + evt.track.kind);
        if (evt.track.kind == 'video') {
            var camIndex = trackCounter++;
            log("Assigning Camera Index: " + camIndex);

            // 1. Create Container
            var container = document.createElement("div");
            container.className = "video-container";

            // 2. Create Video Element
            var videoEl = document.createElement("video");
            videoEl.srcObject = new MediaStream([evt.track]);
            videoEl.autoplay = true;
            videoEl.controls = false; // We use our own controls, or default ones if needed
            videoEl.playsInline = true;

            // 3. Create Controls Panel
            var controlsDiv = document.createElement("div");
            controlsDiv.className = "video-controls";
            controlsDiv.innerHTML = `
                <div class="control-group">
                    <strong>Camera ${camIndex} Focus:</strong>
                    <label>
                        <input type="checkbox" id="chk-auto-${camIndex}" checked onchange="toggleFocus(${camIndex})"> 
                        Auto
                    </label>
                </div>
                <div class="control-group">
                    <input type="range" id="rng-focus-${camIndex}" min="0" max="255" value="0" disabled oninput="updateFocus(${camIndex})">
                    <span id="val-focus-${camIndex}" style="min-width: 30px; text-align: right;">0</span>
                </div>
            `;

            // 4. Assemble
            container.appendChild(videoEl);
            container.appendChild(controlsDiv);
            document.getElementById('videoGrid').appendChild(container);
        }
    };

    // Offer to receive video (we are not sending video)
    pc.addTransceiver('video', { direction: 'recvonly' });
    pc.addTransceiver('video', { direction: 'recvonly' }); // Request 2 tracks / buffers initially

    pc.createOffer().then(function (offer) {
        return pc.setLocalDescription(offer);
    }).then(function () {
        // Wait for ICE gathering to complete
        return new Promise(function (resolve) {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icecandidate', checkState);
                        resolve();
                    }
                }
                pc.addEventListener('icecandidate', checkState);
            }
        });
    }).then(function () {
        var offer = pc.localDescription;

        return fetch('/offer', {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function (response) {
        return response.json();
    }).then(function (answer) {
        btn.innerText = "Stop Streaming";
        btn.className = "btn-stop";
        btn.disabled = false;
        return pc.setRemoteDescription(answer);
    }).catch(function (e) {
        btn.innerText = "Start Streaming";
        btn.className = "";
        btn.disabled = false;
        alert(e);
    });
}

function toggleFocus(camIndex) {
    var isAuto = document.getElementById('chk-auto-' + camIndex).checked;
    var slider = document.getElementById('rng-focus-' + camIndex);
    var valSpan = document.getElementById('val-focus-' + camIndex);

    slider.disabled = isAuto;

    // If switching to manual, send current slider value
    // If switching to auto, value is ignored by server but we send 0
    sendFocus(camIndex, isAuto, slider.value);
}

function updateFocus(camIndex) {
    var slider = document.getElementById('rng-focus-' + camIndex);
    var valSpan = document.getElementById('val-focus-' + camIndex);
    valSpan.innerText = slider.value;

    // Debounce could be good here, but for now we send on input
    sendFocus(camIndex, false, slider.value);
}

function sendFocus(camIndex, isAuto, value) {
    fetch('/set_focus', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            camera_index: camIndex,
            auto: isAuto,
            value: parseInt(value)
        }),
    }).then(response => {
        if (!response.ok) {
            console.error("Failed to set focus");
        }
    });
}
