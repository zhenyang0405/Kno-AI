import { useState, useRef, useCallback } from 'react';

interface AudioRecorderOptions {
    onAudioData?: (chunk: Blob) => void;
}

export function useAudioRecorder(options: AudioRecorderOptions = {}) {
    const [isRecording, setIsRecording] = useState(false);
    const [audioLevel, setAudioLevel] = useState(0);
    const [error, setError] = useState<string | null>(null);

    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const processorRef = useRef<ScriptProcessorNode | null>(null);
    const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const animationFrameRef = useRef<number | null>(null);

    const startRecording = useCallback(async () => {
        try {
            setError(null);
            
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true,
                }
            });
            
            streamRef.current = stream;

            // Create audio context at 16kHz
            const audioContext = new AudioContext({ sampleRate: 16000 });
            audioContextRef.current = audioContext;

            const source = audioContext.createMediaStreamSource(stream);
            sourceRef.current = source;
            
            // Create analyser for audio level visualization
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            analyserRef.current = analyser;
            source.connect(analyser);

            // Start audio level monitoring
            const monitorAudioLevel = () => {
                if (!analyserRef.current) return;
                
                const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
                analyserRef.current.getByteFrequencyData(dataArray);
                
                const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
                setAudioLevel(average / 255);
                
                animationFrameRef.current = requestAnimationFrame(monitorAudioLevel);
            };
            monitorAudioLevel();

            // Use ScriptProcessorNode to capture raw PCM data
            // bufferSize: 4096 samples = ~256ms at 16kHz
            const processor = audioContext.createScriptProcessor(4096, 1, 1);
            processorRef.current = processor;

            processor.onaudioprocess = (e) => {
                if (!options.onAudioData) return;
                
                const inputData = e.inputBuffer.getChannelData(0);
                
                // Convert Float32 to Int16 PCM
                const pcmData = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                
                // Send as blob
                const blob = new Blob([pcmData.buffer], { type: 'audio/pcm' });
                options.onAudioData(blob);
            };

            // Connect: source -> analyser -> processor -> destination
            source.connect(processor);
            processor.connect(audioContext.destination);

            setIsRecording(true);

        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Failed to access microphone';
            setError(errorMessage);
            console.error('Error starting recording:', err);
        }
    }, [options]);

    const stopRecording = useCallback(() => {
        // Disconnect and cleanup processor
        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current.onaudioprocess = null;
            processorRef.current = null;
        }

        // Disconnect and cleanup source
        if (sourceRef.current) {
            sourceRef.current.disconnect();
            sourceRef.current = null;
        }

        // Disconnect analyser
        if (analyserRef.current) {
            analyserRef.current.disconnect();
            analyserRef.current = null;
        }

        // Stop media stream
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }

        // Close audio context
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }

        // Cancel animation frame
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null;
        }

        setIsRecording(false);
        setAudioLevel(0);
    }, []);

    return {
        startRecording,
        stopRecording,
        isRecording,
        audioLevel,
        error,
    };
}
