var pc = null;

function log(msg) {
    document.getElementById('logs').innerText += msg + '\n';
    console.log(msg);
}

function start() {
    var config = {
        sdpSemantics: 'unified-plan'
    };

    // Use Google's STUN server (optional for local network but good practice)
    config.iceServers = [{ urls: ['stun:stun.l.google.com:19302'] }];

    pc = new RTCPeerConnection(config);

    // Dynamic Video Element Creation
    pc.ontrack = function (evt) {
        log("Track received: " + evt.track.kind);
        if (evt.track.kind == 'video') {
            var el = document.createElement("video");
            el.srcObject = new MediaStream([evt.track]);
            el.autoplay = true;
            el.control = true;
            el.playsInline = true;
            document.getElementById('videoGrid').appendChild(el);
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
        return pc.setRemoteDescription(answer);
    }).catch(function (e) {
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
