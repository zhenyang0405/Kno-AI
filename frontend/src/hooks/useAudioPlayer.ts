import { useState, useRef, useCallback } from 'react';

export function useAudioPlayer() {
    const [isPlaying, setIsPlaying] = useState(false);
    const audioContextRef = useRef<AudioContext | null>(null);
    const sourceNodeRef = useRef<AudioBufferSourceNode | null>(null);

    const playAudio = useCallback(async (audioData: ArrayBuffer) => {
        try {
            // Stop any currently playing audio
            stop();

            // Create or reuse audio context
            if (!audioContextRef.current) {
                audioContextRef.current = new AudioContext();
            }

            const audioContext = audioContextRef.current;

            // Decode the audio data
            const audioBuffer = await audioContext.decodeAudioData(audioData);

            // Create source node
            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);

            sourceNodeRef.current = source;

            // Set up event handlers
            source.onended = () => {
                console.log('✅ Audio playback finished');
                setIsPlaying(false);
                sourceNodeRef.current = null;
            };

            // Start playback
            source.start(0);
            setIsPlaying(true);

        } catch (error) {
            console.error('❌ Error playing audio:', error);
            setIsPlaying(false);
        }
    }, []);



    const playBase64Audio = useCallback(async (base64Data: string) => {
        try {
            
            // Decode base64 to ArrayBuffer
            const binaryString = atob(base64Data);
            
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            
            await playAudio(bytes.buffer);
        } catch (error) {
            console.error('❌ Error playing base64 audio:', error);
        }
    }, [playAudio]);

    const nextStartTimeRef = useRef<number>(0);
    const scheduledSourcesRef = useRef<AudioBufferSourceNode[]>([]);

    /**
     * Play raw PCM audio data (Int16, 24kHz, mono)
     * Properly queued for streaming
     */
    const playPCMAudio = useCallback(async (pcmData: ArrayBuffer) => {
        try {
            // Create or reuse audio context
            if (!audioContextRef.current) {
                audioContextRef.current = new AudioContext();
            }

            const audioContext = audioContextRef.current;
            const currentTime = audioContext.currentTime;

            // Reset queue if we've fallen behind (gap in speech)
            if (nextStartTimeRef.current < currentTime) {
                nextStartTimeRef.current = currentTime;
            }

            // Convert raw PCM Int16 to Float32
            const pcmInt16 = new Int16Array(pcmData);
            const numSamples = pcmInt16.length;
            const pcmSampleRate = 24000; // Gemini Live API 24kHz
            
            // Create AudioBuffer
            const audioBuffer = audioContext.createBuffer(1, numSamples, pcmSampleRate);
            const channelData = audioBuffer.getChannelData(0);
            for (let i = 0; i < numSamples; i++) {
                channelData[i] = pcmInt16[i] / (pcmInt16[i] < 0 ? 32768 : 32767);
            }

            // Create source and schedule it
            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);

            // Schedule to start at the end of the previous chunk
            source.start(nextStartTimeRef.current);
            
            // Track source for cleanup
            scheduledSourcesRef.current.push(source);
            source.onended = () => {
                scheduledSourcesRef.current = scheduledSourcesRef.current.filter(s => s !== source);
                if (scheduledSourcesRef.current.length === 0) {
                    setIsPlaying(false);
                }
            };

            // Update next start time
            nextStartTimeRef.current += audioBuffer.duration;
            setIsPlaying(true);

        } catch (error) {
            console.error('❌ Error playing PCM audio:', error);
        }
    }, []);

    const stop = useCallback(() => {
        // Stop all scheduled sources
        scheduledSourcesRef.current.forEach(source => {
            try {
                source.stop();
                source.disconnect();
            } catch (e) { /* ignore */ }
        });
        scheduledSourcesRef.current = [];
        nextStartTimeRef.current = 0;
        
        if (sourceNodeRef.current) {
            try { sourceNodeRef.current.stop(); } catch (e) {}
            sourceNodeRef.current = null;
        }
        setIsPlaying(false);
    }, []);

    return {
        playAudio,
        playBase64Audio,
        playPCMAudio,
        stop,
        isPlaying,
    };
}
