export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface LiveAgentEvent {
    // Binary audio data (raw PCM sent via websocket.send_bytes)
    binaryAudio?: ArrayBuffer;
    
    // Output transcription for text responses
    outputTranscription?: {
        text?: string;
        finished?: boolean;
    };

    // Input transcription (user's speech)
    inputTranscription?: {
        text?: string;
        isFinal?: boolean;
    };
    
    // Content with parts (per ADK docs - this is where audio comes)
    content?: {
        parts?: Array<{
            text?: string;
            inline_data?: {
                mime_type: string;
                data: string; // base64 encoded audio (raw PCM)
            };
        }>;
    };
    
    // Server content - can have multiple formats
    serverContent?: {
        // Direct inline data (for audio)
        inlineData?: {
            mimeType: string;
            data: string; // base64 encoded
        };
        // Model turn with parts
        modelTurn?: {
            parts?: Array<{
                text?: string;
                inlineData?: {
                    mimeType: string;
                    data: string; // base64 encoded audio
                };
            }>;
        };
    };
    
    // Additional fields from ADK events
    partial?: boolean;
    invocationId?: string;
    author?: string;
    toolCall?: any;
    toolCallCancellation?: any;
    actions?: any;
}

export class LiveAgentConnection {
    private ws: WebSocket | null = null;
    private connectionStatus: ConnectionStatus = 'disconnected';
    private eventCallbacks: ((event: LiveAgentEvent) => void)[] = [];
    private statusCallbacks: ((status: ConnectionStatus) => void)[] = [];
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    connect(userId: number, sessionId: number): Promise<void> {
        return new Promise((resolve, reject) => {
            if (this.ws?.readyState === WebSocket.OPEN) {
                resolve();
                return;
            }

            this.setStatus('connecting');
            const wsUrl = `wss://live-active-learning-agent-460848097230.us-east1.run.app/ws/${userId}/${sessionId}`;
            // const wsUrl = `ws://localhost:8004/ws/${userId}/${sessionId}`;

            try {
                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = () => {
                    console.log('✅ WebSocket connected to live agent at:', wsUrl);
                    this.reconnectAttempts = 0;
                    this.setStatus('connected');
                    resolve();
                };

                this.ws.onmessage = (event) => {
                    // Handle binary audio data
                    if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
                        console.log('🎵 Received binary audio data:', event.data);
                        
                        // Convert to ArrayBuffer if needed
                        const processAudioData = async () => {
                            let audioBuffer: ArrayBuffer;
                            
                            if (event.data instanceof Blob) {
                                audioBuffer = await event.data.arrayBuffer();
                            } else {
                                audioBuffer = event.data;
                            }
                            
                            console.log('🎵 Binary audio buffer size:', audioBuffer.byteLength, 'bytes');
                            
                            // Emit as special audio event
                            this.eventCallbacks.forEach(callback => callback({
                                binaryAudio: audioBuffer
                            } as any));
                        };
                        
                        processAudioData().catch(err => {
                            console.error('❌ Error processing binary audio:', err);
                        });
                        
                        return;
                    }
                    
                    // Handle text JSON messages
                    try {
                        const data = JSON.parse(event.data);
                        console.log('📨 Received event from live agent:', data);
                        this.eventCallbacks.forEach(callback => callback(data));
                    } catch (error) {
                        console.error('❌ Error parsing WebSocket message:', error, 'Raw data:', event.data);
                    }
                };

                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.setStatus('error');
                    reject(error);
                };

                this.ws.onclose = () => {
                    console.log('WebSocket disconnected');
                    this.setStatus('disconnected');
                    this.attemptReconnect(userId, sessionId);
                };

            } catch (error) {
                this.setStatus('error');
                reject(error);
            }
        });
    }

    disconnect(): void {
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
        }
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        this.reconnectAttempts = 0;
        this.setStatus('disconnected');
    }

    sendAudio(audioData: Blob): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            // Send audio as binary data
            audioData.arrayBuffer().then(buffer => {
                console.log('🎤 Sending audio chunk:', buffer.byteLength, 'bytes');
                this.ws?.send(buffer);
            });
        } else {
            console.warn('WebSocket not connected, cannot send audio');
        }
    }

    sendText(text: string): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({
                type: 'text',
                text: text
            });
            this.ws.send(message);
        } else {
            console.warn('WebSocket not connected, cannot send text');
        }
    }

    sendImage(base64Data: string, mimeType: string): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({
                type: 'image',
                mimeType: mimeType,
                data: base64Data
            });
            this.ws.send(message);
        } else {
            console.warn('WebSocket not connected, cannot send image');
        }
    }

    onEvent(callback: (event: LiveAgentEvent) => void): () => void {
        this.eventCallbacks.push(callback);
        // Return unsubscribe function
        return () => {
            this.eventCallbacks = this.eventCallbacks.filter(cb => cb !== callback);
        };
    }

    onConnectionStatusChange(callback: (status: ConnectionStatus) => void): () => void {
        this.statusCallbacks.push(callback);
        // Immediately call with current status
        callback(this.connectionStatus);
        // Return unsubscribe function
        return () => {
            this.statusCallbacks = this.statusCallbacks.filter(cb => cb !== callback);
        };
    }

    getStatus(): ConnectionStatus {
        return this.connectionStatus;
    }

    private setStatus(status: ConnectionStatus): void {
        this.connectionStatus = status;
        this.statusCallbacks.forEach(callback => callback(status));
    }

    private attemptReconnect(userId: number, sessionId: number): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnect attempts reached');
            return;
        }

        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
        this.reconnectAttempts++;

        console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        this.reconnectTimeout = setTimeout(() => {
            this.connect(userId, sessionId).catch(error => {
                console.error('Reconnect failed:', error);
            });
        }, delay);
    }
}
