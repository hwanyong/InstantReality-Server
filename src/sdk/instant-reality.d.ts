/**
 * InstantReality WebRTC Client SDK
 * 
 * Provides a simple interface to connect to the InstantReality server and consume
 * multi-camera streams via WebRTC. Cameras are identified by role names (e.g. 'TopView').
 */

export interface InstantRealityOptions {
    /** URL of the signaling server (e.g. http://localhost:8080) */
    serverUrl?: string
    /** Maximum number of cameras to support (default: 4) */
    maxCameras?: number
    /** ICE servers configuration (default: Google STUN) */
    iceServers?: RTCIceServer[]
}

export interface ConnectOptions {
    /** List of role names to enable initially */
    cameras?: string[]
    /** List of role names to request from server */
    roles?: string[]
}

export interface FocusOptions {
    /** Enable auto-focus (default: true) */
    auto?: boolean
    /** Focus value 0-255 (used if auto is false) */
    value?: number
}

export interface AutoExposureOptions {
    /** Enable auto exposure logic on server */
    enabled?: boolean
    /** Target brightness 0-255 (default: 128) */
    targetBrightness?: number
}

/**
 * Main SDK Class
 */
export class InstantReality {
    /**
     * Creates a new InstantReality client instance.
     * @param options Configuration options
     */
    constructor(options?: InstantRealityOptions)

    serverUrl: string
    maxCameras: number
    iceServers: RTCIceServer[]
    clientId: string | null

    // Event Listeners (Typed)
    on(event: 'track', callback: (track: MediaStreamTrack, role: string) => void): this
    on(event: 'connected', callback: () => void): this
    on(event: 'disconnected', callback: () => void): this
    on(event: 'error', callback: (error: Error) => void): this
    on(event: 'trackEnabled', callback: (role: string) => void): this
    on(event: 'trackDisabled', callback: (role: string) => void): this
    on(event: 'cameraChange', callback: (cameras: any) => void): this
    on(event: 'roleMapReady', callback: (roleMap: object) => void): this
    // Fallback for other events
    on(event: string, callback: (...args: any[]) => void): this

    off(event: string, callback: (...args: any[]) => void): this

    /**
     * Fetch current role→camera mapping from server.
     */
    getRoles(): Promise<object>

    /**
     * Get roles that are currently connected (have active tracks).
     */
    getConnectedRoles(): string[]

    /**
     * Get the MediaStreamTrack for a specific role.
     * @param role Role name (e.g. 'TopView')
     */
    getTrack(role: string): MediaStreamTrack | null

    /**
     * Connects to the server and negotiates WebRTC.
     * @param options Connection options
     */
    connect(options?: ConnectOptions): Promise<this>

    /**
     * Disconnects and closes the peer connection.
     */
    disconnect(): this

    /**
     * Reconnects using the last connection options.
     */
    reconnect(): Promise<this>

    /**
     * Enables or disables a specific camera track by role.
     * Pausing a track will notify the server to stop sending data.
     * @param role Role name (e.g. 'TopView')
     * @param enabled True to enable, false to disable
     */
    setTrackEnabled(role: string, enabled: boolean): Promise<boolean>

    /**
     * Checks if a track is enabled for the given role.
     * @param role Role name
     */
    isTrackEnabled(role: string): boolean

    /**
     * Controls camera focus (if supported).
     * @param role Role name
     */
    setFocus(role: string, options?: FocusOptions): Promise<any>

    /**
     * Sets manual exposure value.
     * @param role Role name
     */
    setExposure(role: string, value: number): Promise<any>

    /**
     * Configures server-side auto-exposure logic.
     * @param role Role name
     */
    setAutoExposure(role: string, options?: AutoExposureOptions): Promise<any>

    /**
     * Captures a single frame from the specified camera.
     * @param role Role name
     * @returns Blob of the captured image
     */
    capture(role: string): Promise<Blob>
}

export default InstantReality
