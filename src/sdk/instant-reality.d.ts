/**
 * InstantReality WebRTC Client SDK
 * 
 * Provides a simple interface to connect to the InstantReality server and consume
 * multi-camera streams via WebRTC.
 */

export interface InstantRealityOptions {
    /** URL of the signaling server (e.g. http://localhost:8080) */
    serverUrl?: string;
    /** Maximum number of cameras to support (default: 4) */
    maxCameras?: number;
    /** ICE servers configuration (default: Google STUN) */
    iceServers?: RTCIceServer[];
}

export interface ConnectOptions {
    /** List of camera indices to enable initially */
    cameras?: number[];
}

export interface FocusOptions {
    /** Enable auto-focus (default: true) */
    auto?: boolean;
    /** Focus value 0-255 (used if auto is false) */
    value?: number;
}

export interface AutoExposureOptions {
    /** Enable auto exposure logic on server */
    enabled?: boolean;
    /** Target brightness 0-255 (default: 128) */
    targetBrightness?: number;
}

/**
 * Main SDK Class
 */
export class InstantReality {
    /**
     * Creates a new InstantReality client instance.
     * @param options Configuration options
     */
    constructor(options?: InstantRealityOptions);

    serverUrl: string;
    maxCameras: number;
    iceServers: RTCIceServer[];
    clientId: string | null;

    // Event Listeners (Typed)
    on(event: 'track', callback: (track: MediaStreamTrack, index: number) => void): this;
    on(event: 'connected', callback: () => void): this;
    on(event: 'disconnected', callback: () => void): this;
    on(event: 'error', callback: (error: Error) => void): this;
    on(event: 'trackEnabled', callback: (index: number) => void): this;
    on(event: 'trackDisabled', callback: (index: number) => void): this;
    // Fallback for other events
    on(event: string, callback: (...args: any[]) => void): this;

    off(event: string, callback: (...args: any[]) => void): this;

    /**
     * Connects to the server and negotiates WebRTC.
     * @param options Connection options
     */
    connect(options?: ConnectOptions): Promise<this>;

    /**
     * Disconnects and closes the peer connection.
     */
    disconnect(): this;

    /**
     * Enables or disables a specific camera track.
     * Pausing a track will notify the server to stop sending data for that camera.
     * @param cameraIndex Index of the camera (0-based)
     * @param enabled True to enable, false to disable
     */
    setTrackEnabled(cameraIndex: number, enabled: boolean): Promise<boolean>;

    /**
     * Checks if a local track is enabled.
     * @param cameraIndex Index of the camera
     */
    isTrackEnabled(cameraIndex: number): boolean;

    /**
     * Controls camera focus (if supported).
     */
    setFocus(cameraIndex: number, options?: FocusOptions): Promise<any>;

    /**
     * sets manual exposure value.
     */
    setExposure(cameraIndex: number, value: number): Promise<any>;

    /**
     * Configures server-side auto-exposure logic.
     */
    setAutoExposure(cameraIndex: number, options?: AutoExposureOptions): Promise<any>;

    /**
     * Captures a single frame from the specified camera.
     * @param cameraIndex Index of the camera
     * @returns Blob of the captured image
     */
    capture(cameraIndex: number): Promise<Blob>;
}

export default InstantReality;
