import { useState, useEffect, useRef, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getDocumentDownloadUrl } from '../services/api';
import type { DocumentItem } from '../types';
import { initializeWorkspace, initializeSession, type ContentResponse } from '../services/activeLearning';
import { LiveAgentConnection, type ConnectionStatus } from '../services/liveAgent';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import "@excalidraw/excalidraw/index.css";

// Set the worker source for PDF.js
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface Message {
    id: string;
    role: 'user' | 'assistant';
    text?: string;
    content?: ContentResponse['content'];
    timestamp: number;
}

interface ActiveLearningWorkspaceProps {
    selectedDoc: DocumentItem;
    knowledgeId: string;
    topicId: string;
    studySessionId: number | null;  // Pass from parent
    userId: number | null;           // Pass from parent
    onBack: () => void;
}

type LayoutState = 'reading' | 'deep-dive';

export default function ActiveLearningWorkspace({ 
    selectedDoc, 
    knowledgeId, 
    topicId,
    studySessionId,
    userId,
    onBack 
}: ActiveLearningWorkspaceProps) {
    const [layoutState, setLayoutState] = useState<LayoutState>('reading');
    const [resolvedUrl, setResolvedUrl] = useState<string | null>(null);
    const [numPages, setNumPages] = useState<number | null>(null);
    const [scale, setScale] = useState(1.0);
    const [containerWidth, setContainerWidth] = useState<number>(0);
    const containerRef = useRef<HTMLDivElement>(null);

    const [glowZones, setGlowZones] = useState<number[]>([]);
    
    // New state for API integration

    const [messages, setMessages] = useState<Message[]>([]);
    const [activeTab, setActiveTab] = useState<'animation' | 'image' | 'board' | 'live'>('live');
    const [Excalidraw, setExcalidraw] = useState<any>(null);

    // LIVE tab state
    const [liveConnection] = useState(() => new LiveAgentConnection());
    const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
    const [liveTranscripts, setLiveTranscripts] = useState<Array<{ role: 'user' | 'assistant', text: string, timestamp: number }>>([]);
    
    // Screen sharing state
    const [isScreenSharing, setIsScreenSharing] = useState(false);
    const screenVideoRef = useRef<HTMLVideoElement | null>(null);
    const screenCanvasRef = useRef<HTMLCanvasElement | null>(null);
    const screenShareIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const liveConnectionRef = useRef<LiveAgentConnection>(liveConnection);

    // Audio hooks
    const { startRecording, stopRecording, isRecording, audioLevel } = useAudioRecorder({
        onAudioData: (chunk) => {
            liveConnectionRef.current.sendAudio(chunk);
        }
    });
    const { playBase64Audio, playPCMAudio, isPlaying } = useAudioPlayer();

    // Dynamic import for Excalidraw to avoid SSR/Initial load issues if any
    useEffect(() => {
        import('@excalidraw/excalidraw').then((comp) => {
            setExcalidraw(comp.Excalidraw);
        });
    }, []);
    
    // Log the IDs for now to satisfy lint and show they are being used
    useEffect(() => {
        console.log(`Knowledge: ${knowledgeId}, Topic: ${topicId}`);
    }, [knowledgeId, topicId]);

    useEffect(() => {
        const fetchUrl = async () => {
            try {
                // Get signed download URL from API
                const url = await getDocumentDownloadUrl(selectedDoc.id);
                setResolvedUrl(url);
            } catch (error) {
                console.error("Error fetching document URL:", error);
            }
        };
        fetchUrl();
    }, [selectedDoc]);

    // Handle container resize for PDF scaling
    useEffect(() => {
        if (!containerRef.current) return;

        const observer = new ResizeObserver((entries) => {
            if (entries[0]) {
                // Adjust for padding (p-4 = 16px on each side)
                setContainerWidth(entries[0].contentRect.width - 32);
            }
        });

        observer.observe(containerRef.current);
        return () => observer.disconnect();
    }, []);

    // Initialize workspace: triggers cache creation and concept extraction in background
    useEffect(() => {
        const initWorkspace = async () => {
            try {
                // Don't initialize if we don't have required IDs yet
                if (!studySessionId || !userId) {
                    console.warn('Missing studySessionId or userId, skipping workspace initialization');
                    return;
                }
                
                console.log('Initializing active learning workspace...');
                // 1. Initialize backend storage/cache (port 8001)
                const result = await initializeWorkspace({
                    study_session_id: studySessionId,
                    user_id: userId
                });
                
                console.log('Workspace initialized:', result);
                
                // 2. Initialize agent session and get intro message (port 8002)

                const introResponse = await initializeSession({
                    session_id: studySessionId,
                    user_id: userId
                });
                
                console.log('Session initialized:', introResponse);
                
                // Add intro message to chat
                const introMsg: Message = {
                    id: 'intro-' + Date.now().toString(),
                    role: 'assistant',
                    text: introResponse.chat_response,
                    content: introResponse.content || undefined,
                    timestamp: Date.now()
                };
                
                setMessages([introMsg]);
                
            } catch (error) {
                console.error('Failed to initialize workspace or session:', error);
            }
        };
        
        initWorkspace();
    }, [studySessionId, userId]); // Re-run if IDs change

    // Cleanup screen share on unmount
    useEffect(() => {
        return () => {
             if (screenShareIntervalRef.current) {
                clearInterval(screenShareIntervalRef.current);
             }
             if (screenVideoRef.current && screenVideoRef.current.srcObject) {
                 const tracks = (screenVideoRef.current.srcObject as MediaStream).getTracks();
                 tracks.forEach(track => track.stop());
             }
        };
    }, []);

    // Screen sharing logic
    const toggleScreenShare = useCallback(async () => {
        if (isScreenSharing) {
            // Stop sharing
            if (screenShareIntervalRef.current) {
                clearInterval(screenShareIntervalRef.current);
                screenShareIntervalRef.current = null;
            }
            if (screenVideoRef.current && screenVideoRef.current.srcObject) {
                const tracks = (screenVideoRef.current.srcObject as MediaStream).getTracks();
                tracks.forEach(track => track.stop());
                screenVideoRef.current.srcObject = null;
            }
            setIsScreenSharing(false);
        } else {
            // Start sharing
            try {
                const stream = await navigator.mediaDevices.getDisplayMedia({ 
                    video: { cursor: "always" } as any, 
                    audio: false 
                });
                
                if (screenVideoRef.current) {
                    screenVideoRef.current.srcObject = stream;
                    await screenVideoRef.current.play(); // Ensure it's playing so we can capture frames
                }
                
                // Handle stream end (user clicks "Stop sharing" in browser UI)
                stream.getVideoTracks()[0].onended = () => {
                   if (screenShareIntervalRef.current) {
                       clearInterval(screenShareIntervalRef.current);
                       screenShareIntervalRef.current = null;
                   }
                   if (screenVideoRef.current) {
                       screenVideoRef.current.srcObject = null;
                   }
                   setIsScreenSharing(false);
                };

                setIsScreenSharing(true);
                
                // Start capturing frames
                screenShareIntervalRef.current = setInterval(() => {
                    if (screenVideoRef.current && screenCanvasRef.current && liveConnection) {
                         const video = screenVideoRef.current;
                         const canvas = screenCanvasRef.current;
                         const ctx = canvas.getContext('2d');
                         
                         if (ctx && video.videoWidth > 0) {
                             // Resize canvas to match video, downscale if huge
                             const maxDim = 1024;
                             const scale = Math.min(1, maxDim / Math.max(video.videoWidth, video.videoHeight));
                             canvas.width = video.videoWidth * scale;
                             canvas.height = video.videoHeight * scale;
                             
                             ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                             
                             // Get base64 (JPEG quality 0.6)
                             const dataUrl = canvas.toDataURL('image/jpeg', 0.6);
                             const base64Data = dataUrl.split(',')[1];
                             liveConnection.sendImage(base64Data, 'image/jpeg');
                         }
                    }
                }, 1000); // Send 1 FPS checking screen
                
            } catch (err) {
                console.error("Error starting screen share:", err);
            }
        }
    }, [isScreenSharing, liveConnection]);

    // LIVE connection status listener
    useEffect(() => {
        const unsubscribe = liveConnection.onConnectionStatusChange((status) => {
            setConnectionStatus(status);
        });
        return unsubscribe;
    }, [liveConnection]);

    // LIVE event listener
    useEffect(() => {
        const unsubscribe = liveConnection.onEvent((event) => {
            
            // Handle binary PCM audio (sent via websocket.send_bytes)
            if (event.binaryAudio) {
                playPCMAudio(event.binaryAudio);
                return; // Binary audio is separate from other events
            }
            
            // Handle input transcription (user's speech)
            const inputTranscription = event.inputTranscription || (event as any).input_transcription;
            
            if (inputTranscription?.text) {
                const text = inputTranscription.text;
                // Check all possible casing for finality flag just in case
                const isFinal = (inputTranscription as any).isFinal || 
                               (inputTranscription as any).is_final || 
                               (inputTranscription as any).finished;
                
                // Only add to transcript when final to avoid clutter
                // (or optimize to update in-place for live effect later)
                if (text && text.trim().length > 0) {
                     setLiveTranscripts(prev => {
                        // We will only commit to the list if it's FINAL. 
                        // To show realtime, we'd need a separate "currentInput" state.
                        if (isFinal) {
                            return [...prev, {
                                role: 'user',
                                text: text,
                                timestamp: Date.now()
                            }];
                        }
                        return prev;
                     });
                }
            }

            // Handle output transcription (text responses)
            if (event.outputTranscription?.text) {
                const text = event.outputTranscription.text;
                const isFinished = event.outputTranscription.finished;
                
                // Only add to transcript when finished
                if (isFinished) {
                    setLiveTranscripts(prev => [...prev, {
                        role: 'assistant',
                        text: text,
                        timestamp: Date.now()
                    }]);
                }
            }
            
            // Handle audio from event.content.parts (per ADK docs)
            if (event.content?.parts) {
                for (const part of event.content.parts) {
                    // Check for inline audio data
                    if (part.inline_data?.mime_type?.startsWith('audio/') && part.inline_data.data) {
                        playBase64Audio(part.inline_data.data);
                    }
                }
            }
            
            // Handle server content (alternative structure)
            if (event.serverContent) {
                // Check for inline data (audio)
                if (event.serverContent.inlineData) {
                    const inlineData = event.serverContent.inlineData;
                    if (inlineData.mimeType?.startsWith('audio/') && inlineData.data) {
                        playBase64Audio(inlineData.data);
                    }
                }
                
                // Also check modelTurn structure
                if (event.serverContent.modelTurn?.parts) {
                    for (const part of event.serverContent.modelTurn.parts) {
                        if (part.text) {
                            setLiveTranscripts(prev => [...prev, {
                                role: 'assistant',
                                text: part.text!,
                                timestamp: Date.now()
                            }]);
                        }
                        
                        if (part.inlineData?.mimeType?.startsWith('audio/') && part.inlineData.data) {
                            playBase64Audio(part.inlineData.data);
                        }
                    }
                }
            }
        });
        return unsubscribe;
    }, [liveConnection, playBase64Audio]);

    // Cleanup LIVE connection on unmount
    useEffect(() => {
        return () => {
            liveConnection.disconnect();
        };
    }, [liveConnection]);



    const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
        setNumPages(numPages);
    };



    // Calculate zone widths based on layout state
    const getZoneWidths = () => {
        switch (layoutState) {
            case 'reading': return { anchor: 'w-[60%]', workshop: 'w-[40%]' };
            case 'deep-dive': return { anchor: 'w-[40%]', workshop: 'w-[60%]' };
            default: return { anchor: 'w-[40%]', workshop: 'w-[60%]' };
        }
    };

    const widths = getZoneWidths();

    return (
        <div className="fixed inset-0 z-50 bg-zinc-950 flex flex-col font-sans text-zinc-300 overflow-hidden">
            {/* Top Strip: Session Info */}
            <header className="h-12 border-b border-zinc-800 flex items-center justify-between px-6 bg-zinc-900/50 backdrop-blur-md">
                <div className="flex items-center space-x-6">
                    <button onClick={onBack} className="text-zinc-500 hover:text-white transition-colors">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                
                    {selectedDoc.filename}
                
                <div className="flex items-center space-x-6">
                    {/* Layout Mode Selector */}
                    <div className="flex bg-zinc-800/50 rounded-lg p-1 border border-zinc-700/50">
                        {(['reading', 'deep-dive'] as const).map((mode) => (
                            <button
                                key={mode}
                                onClick={() => setLayoutState(mode)}
                                className={`px-3 py-1 rounded text-[10px] font-bold uppercase transition-all ${
                                    layoutState === mode 
                                        ? 'bg-zinc-700 text-white shadow-sm' 
                                        : 'text-zinc-500 hover:text-zinc-300'
                                }`}
                            >
                                {mode.replace('-', ' ')}
                            </button>
                        ))}
                    </div>
                </div>
            </header>

            {/* Main Workspace */}
            <main className="flex-1 flex overflow-hidden relative">
                {/* Background Grid */}
                <div className="absolute inset-0 pointer-events-none opacity-5 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]" />

                {/* ZONE 1: ANCHOR (Left) */}
                <section className={`${widths.anchor} h-full border-r border-zinc-800/50 transition-all duration-700 ease-in-out relative flex flex-col bg-zinc-900/20`}>
                    <div ref={containerRef} className="flex-1 overflow-auto p-4 scrollbar-hide">
                        {resolvedUrl && (
                            <Document file={resolvedUrl} onLoadSuccess={onDocumentLoadSuccess} className="flex flex-col items-center">
                                {numPages && Array.from(new Array(numPages), (_, index) => (
                                    <div key={`page_${index + 1}`} className="relative group">
                                        <Page 
                                            pageNumber={index + 1} 
                                            width={containerWidth ? containerWidth * scale : undefined}
                                            className={`mb-4 shadow-2xl transition-all duration-700 ${glowZones.includes(index + 1) ? 'animate-glow-pulse ring-2 ring-blue-500/50' : 'border border-transparent'}`}
                                            renderAnnotationLayer={false}
                                            renderTextLayer={true}
                                        />
                                        {/* Demo toggle for glow */}
                                        <button 
                                            onClick={() => setGlowZones(curr => curr.includes(index + 1) ? curr.filter(i => i !== index + 1) : [...curr, index + 1])}
                                            className="absolute -right-8 top-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 text-zinc-600 hover:text-blue-500"
                                            title="Toggle Focus Glow"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                                                <path d="M10 2a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 2ZM10 15a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 15ZM10 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6ZM15.657 5.404a.75.75 0 1 0-1.06-1.06l-1.061 1.06a.75.75 0 0 0 1.06 1.06l1.06-1.06ZM6.464 14.596a.75.75 0 1 0-1.06-1.06l-1.06 1.06a.75.75 0 0 0 1.06 1.06l1.06-1.06ZM18 10a.75.75 0 0 1-.75.75h-1.5a.75.75 0 0 1 0-1.5h1.5A.75.75 0 0 1 18 10ZM5 10a.75.75 0 0 1-.75.75h-1.5a.75.75 0 0 1 0-1.5h1.5A.75.75 0 0 1 5 10ZM14.596 15.657a.75.75 0 0 0 1.06-1.06l-1.06-1.06a.75.75 0 0 0-1.06 1.06l1.06 1.06ZM5.404 6.464a.75.75 0 0 0 1.06-1.06l-1.06-1.06a.75.75 0 0 0-1.06 1.06l1.06 1.06Z" />
                                            </svg>
                                        </button>
                                    </div>
                                ))}
                            </Document>
                        )}
                    </div>

                    {/* Anchor Zoom Controls */}
                    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center bg-zinc-900/80 backdrop-blur-md p-1.5 rounded-full border border-zinc-800 shadow-2xl z-20">
                        <div className="w-[1px] h-4 bg-zinc-800 mx-1" />
                        <div className="flex items-center space-x-1">
                            <button 
                                onClick={() => setScale(prev => Math.max(0.3, prev - 0.1))}
                                className="p-1.5 rounded-full hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12h-15" />
                                </svg>
                            </button>
                            <span className="text-[10px] font-mono text-zinc-500 min-w-[35px] text-center">
                                {Math.round(scale * 100)}%
                            </span>
                            <button 
                                onClick={() => setScale(prev => Math.min(2.0, prev + 0.1))}
                                className="p-1.5 rounded-full hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                                </svg>
                            </button>
                        </div>
                    </div>
                </section>

                {/* ZONE 2: WORKSHOP (Center) */}
                <section className={`${widths.workshop} h-full transition-all duration-700 ease-in-out flex flex-col relative`}>
                    <div className="w-full flex-none px-6 py-4 border-b border-zinc-800/50 bg-zinc-900/50 backdrop-blur-sm z-10 flex items-center justify-between">
                         <div className="flex items-center space-x-2">
                        
                        {/* Tab Switcher */}
                        {(['animation', 'image', 'board', 'live'] as const).map((tab) => {
                            // Check if content exists for this tab (always show board and live)
                            const hasContent = tab === 'board' || tab === 'live' ? true : messages.some(m => m.content?.type === tab);
                            const count = messages.filter(m => m.content?.type === tab).length;

                            if (!hasContent) return null;

                            return (
                                <button
                                    key={tab}
                                    onClick={() => setActiveTab(tab)}
                                    className={`
                                        px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border transition-all flex items-center space-x-1.5
                                        ${activeTab === tab 
                                            ? 'bg-blue-600/20 text-blue-400 border-blue-500/30 shadow-lg shadow-blue-900/20' 
                                            : 'bg-zinc-900/50 text-zinc-500 border-zinc-800 hover:text-zinc-300 hover:border-zinc-700'
                                        }
                                    `}
                                >
                                    <span>{tab}</span>
                                    {count > 0 && (
                                        <span className={`px-1 rounded-full text-[8px] ${activeTab === tab ? 'bg-blue-500/20 text-blue-300' : 'bg-zinc-800 text-zinc-600'}`}>
                                            {count}
                                        </span>
                                    )}
                                </button>
                            );
                        })}
                        </div>
                    </div>
                    
                    <div className={`flex-1 overflow-y-auto flex flex-col ${(activeTab === 'board' || activeTab === 'live') ? 'p-0 overflow-hidden' : 'p-2 items-center'}`}>
                        <div className={`w-full flex flex-col ${(activeTab === 'board' || activeTab === 'live') ? 'h-full' : 'max-w-3xl space-y-8 pb-20'}`}>
                            
                            {/* TAB CONTENT: CHAT */}


                            {/* TAB CONTENT: ANIMATION */}
                            {activeTab === 'animation' && (
                                <div className="w-full flex-1 flex flex-col animate-in fade-in duration-300">
                                    {(() => {
                                        // Find latest animation
                                        const latestAnim = [...messages].reverse().find(m => m.content?.type === 'animation');
                                        if (!latestAnim || !latestAnim.content) return <div className="text-zinc-500 text-center mt-20">No animations generated yet.</div>;
                                        
                                        return (
                                            <div className="flex flex-col space-y-4">
                                                <div className="w-full aspect-video bg-zinc-950 rounded-xl overflow-hidden border border-zinc-800 relative shadow-2xl">
                                                    <iframe 
                                                        srcDoc={latestAnim.content.data} 
                                                        className="w-full h-full border-none"
                                                        title="Animation Preview"
                                                    />
                                                </div>
                                                <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800">
                                                    <h3 className="text-lg font-bold text-white mb-2">{latestAnim.content.concept_name || "Generated Animation"}</h3>
                                                    <p className="text-zinc-400 text-sm">Generated on {new Date(latestAnim.timestamp).toLocaleTimeString()}</p>
                                                </div>
                                            </div>
                                        );
                                    })()}
                                </div>
                            )}

                            {/* TAB CONTENT: IMAGE */}
                            {activeTab === 'image' && (
                                <div className="w-full flex-1 flex flex-col animate-in fade-in duration-300">
                                    {(() => {
                                        // Find latest image
                                        const latestImg = [...messages].reverse().find(m => m.content?.type === 'image');
                                        if (!latestImg || !latestImg.content) return <div className="text-zinc-500 text-center mt-20">No images generated yet.</div>;
                                        
                                        return (
                                            <div className="flex flex-col space-y-4">
                                                <div className="w-full bg-zinc-950 rounded-xl overflow-hidden border border-zinc-800 relative shadow-2xl">
                                                     {/* Robust Image Rendering */}
                                                     {(() => {
                                                         const getContentSrc = (content: any) => {
                                                             const data = content.data;
                                                             if (!data) return '';
                                                             
                                                             // Case 1: Raw SVG string
                                                             if (typeof data === 'string' && data.trim().startsWith('<svg')) {
                                                                 return `data:image/svg+xml;utf8,${encodeURIComponent(data)}`;
                                                             }
                                                             
                                                             // Case 2: Already a Data URI or URL
                                                             if (data.startsWith('data:') || data.startsWith('http')) {
                                                                 return data;
                                                             }
                                                             
                                                             // Case 3: Base64 string (missing prefix)
                                                             // Default to PNG if format not specified or strangely specified
                                                             const format = content.metadata?.format === 'svg' ? 'svg+xml' : (content.metadata?.format || 'png');
                                                             return `data:image/${format};base64,${data}`;
                                                         };

                                                         return (
                                                             <img 
                                                                src={getContentSrc(latestImg.content)} 
                                                                alt={latestImg.content.concept_name || "Generated Concept"} 
                                                                className="w-full h-auto bg-white/5" // Add subtle background for transparent images
                                                             />
                                                         );
                                                     })()}
                                                </div>
                                                <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800">
                                                    <h3 className="text-lg font-bold text-white mb-2">{latestImg.content.concept_name || "Generated Image"}</h3>
                                                    <p className="text-zinc-400 text-sm">Generated on {new Date(latestImg.timestamp).toLocaleTimeString()}</p>
                                                </div>
                                            </div>
                                        );
                                    })()}
                                </div>
                            )}

                            {/* TAB CONTENT: BOARD (Excalidraw) */}
                            {activeTab === 'board' && (
                                <div className="w-full flex-1 flex flex-col animate-in fade-in duration-300 h-full">
                                    <div className="w-full h-full bg-white relative shadow-2xl">
                                        {Excalidraw ? (
                                            <Excalidraw 
                                                theme="light"
                                                initialData={{
                                                    appState: { 
                                                        viewBackgroundColor: "#ffffff",
                                                        currentItemStrokeColor: "#000000",
                                                        currentItemBackgroundColor: "transparent",
                                                    }
                                                }}
                                            />
                                        ) : (
                                            <div className="flex items-center justify-center h-full text-zinc-500">
                                                Loading Whiteboard...
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* TAB CONTENT: LIVE */}
                            {activeTab === 'live' && (
                                <div className="w-full h-full flex flex-col relative">
                                    {/* STATUS INDICATOR (Floating Top Left) */}
                                    <div className="absolute top-4 left-4 z-20 flex items-center space-x-2 bg-zinc-900/80 backdrop-blur-md px-3 py-1.5 rounded-full border border-zinc-800 shadow-lg">
                                        <div className={`w-2 h-2 rounded-full ${
                                            connectionStatus === 'connected' ? 'bg-green-500 animate-pulse' :
                                            connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' :
                                            connectionStatus === 'error' ? 'bg-red-500' :
                                            'bg-zinc-600'
                                        }`} />
                                        <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
                                            {connectionStatus}
                                        </span>
                                    </div>

                                    {/* CONNECT BUTTON (Floating Top Right) */}
                                    <button
                                        onClick={() => {
                                            if (connectionStatus === 'connected') {
                                                liveConnection.disconnect();
                                            } else if (studySessionId && userId) {
                                                liveConnection.connect(userId, studySessionId);
                                            }
                                        }}
                                        className={`absolute top-4 right-4 z-20 px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider transition-all shadow-lg ${
                                            connectionStatus === 'connected' 
                                                ? 'bg-zinc-800 text-red-400 hover:bg-zinc-700 border border-zinc-700' 
                                                : 'bg-blue-600 text-white hover:bg-blue-700 shadow-blue-500/20'
                                        }`}
                                    >
                                        {connectionStatus === 'connected' ? 'Disconnect' : 'Connect'}
                                    </button>

                                    {/* MAIN CONVERSATION AREA */}
                                    <div className="flex-1 overflow-y-auto px-4 py-6 md:px-12 scrollbar-hide flex flex-col items-center">
                                        <div className="w-full max-w-2xl space-y-6 pb-32">
                                            {liveTranscripts.length === 0 ? (
                                                <div className="flex flex-col items-center justify-center min-h-[50vh] text-center space-y-6 opacity-0 animate-in fade-in slide-in-from-bottom-4 duration-700">
                                                    <div className="w-24 h-24 rounded-full bg-gradient-to-tr from-blue-600/20 to-indigo-600/20 flex items-center justify-center shadow-inner border border-white/5">
                                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor" className="w-10 h-10 text-blue-400 opacity-80">
                                                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                                                        </svg>
                                                    </div>
                                                    <div className="space-y-2">
                                                        <h3 className="text-2xl font-semibold text-zinc-200 tracking-tight">AI Tutor Live</h3>
                                                        <p className="text-zinc-500 max-w-xs mx-auto text-sm leading-relaxed">
                                                            Connect to start a real-time voice conversation. Ask questions, discuss topics, or practice concepts.
                                                        </p>
                                                    </div>
                                                    {connectionStatus === 'disconnected' && (
                                                         <button
                                                            onClick={() => {
                                                                if (studySessionId && userId) {
                                                                    liveConnection.connect(userId, studySessionId);
                                                                }
                                                            }}
                                                            className="px-6 py-2.5 bg-white text-black hover:bg-zinc-200 rounded-full text-sm font-bold transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5 animate-pulse"
                                                        >
                                                            Start Session
                                                        </button>
                                                    )}
                                                </div>
                                            ) : (
                                                liveTranscripts.map((transcript, idx) => (
                                                    <div key={idx} className={`flex ${transcript.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-500`}>
                                                        <div className={`max-w-[85%] relative group ${
                                                            transcript.role === 'user' 
                                                                ? 'items-end flex flex-col' 
                                                                : 'items-start flex flex-col'
                                                        }`}>
                                                            {/* Label */}
                                                            <span className={`text-[10px] font-medium mb-1.5 opacity-40 uppercase tracking-widest ${transcript.role === 'user' ? 'mr-1' : 'ml-1'}`}>
                                                                {transcript.role === 'user' ? 'You' : 'AI Tutor'}
                                                            </span>

                                                            {/* Bubble */}
                                                            <div className={`px-6 py-4 rounded-2xl shadow-sm text-base leading-relaxed ${
                                                                transcript.role === 'user' 
                                                                    ? 'bg-blue-600 text-white rounded-tr-sm'
                                                                    : 'bg-zinc-800/80 text-zinc-200 border border-zinc-700/50 rounded-tl-sm backdrop-blur-sm'
                                                            }`}>
                                                                <ReactMarkdown 
                                                                    remarkPlugins={[remarkGfm]}
                                                                    components={{
                                                                        p: ({node, ...props}) => <p {...props} className="m-0" />,
                                                                        img: ({node, ...props}) => {
                                                                            const [imgError, setImgError] = useState(false);
                                                                            
                                                                            if (imgError) {
                                                                                return (
                                                                                    <div className="p-4 bg-zinc-900/50 rounded-lg border border-red-500/20 text-red-400 text-xs flex items-center space-x-2 my-2">
                                                                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                                                                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                                                                                        </svg>
                                                                                        <span>Failed to load image. URL signature might be expired or invalid.</span>
                                                                                    </div>
                                                                                );
                                                                            }

                                                                            return (
                                                                                <img 
                                                                                    {...props} 
                                                                                    className="rounded-lg shadow-md border border-zinc-700/50 my-3 max-w-full h-auto object-contain bg-black/20" 
                                                                                    alt={props.alt || "Generated Image"}
                                                                                    onError={() => setImgError(true)}
                                                                                />
                                                                            );
                                                                        }
                                                                    }}
                                                                >
                                                                    {transcript.text}
                                                                </ReactMarkdown>
                                                            </div>
                                                            <span className="text-[9px] text-zinc-600 mt-1 opacity-0 group-hover:opacity-100 transition-opacity px-1">
                                                                {new Date(transcript.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                                            </span>
                                                        </div>
                                                    </div>
                                                ))
                                            )}
                                            {/* Dummy div for auto-scroll could go here */}
                                        </div>
                                    </div>

                                    {/* BOTTOM CONTROL BAR */}
                                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 z-50 flex items-center bg-zinc-900/90 backdrop-blur-xl p-2 pr-6 pl-6 rounded-full border border-white/10 shadow-2xl space-x-6">
                                        


                                        {/* Center Mic Button */}
                                        <div className="relative group">
                                            {/* Ripple Effect for active state */}
                                            {isRecording && (
                                                <>
                                                    <div className="absolute inset-0 bg-red-500/30 rounded-full animate-ping" />
                                                    <div className="absolute -inset-2 bg-red-500/20 rounded-full animate-pulse" />
                                                </>
                                            )}
                                            
                                            <button
                                                onClick={() => {
                                                    if (isRecording) {
                                                        stopRecording();
                                                    } else {
                                                        startRecording();
                                                    }
                                                }}
                                                disabled={connectionStatus !== 'connected' || isPlaying}
                                                className={`relative z-10 w-14 h-14 rounded-full flex items-center justify-center transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed ${
                                                    isRecording
                                                        ? 'bg-red-500 shadow-xl shadow-red-500/40 text-white'
                                                        : connectionStatus !== 'connected' 
                                                            ? 'bg-zinc-700 text-zinc-400 shadow-inner'
                                                            : 'bg-white text-black shadow-xl hover:shadow-white/20'
                                                }`}
                                            >
                                                {isRecording ? (
                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
                                                        <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 7.5A2.25 2.25 0 017.5 5.25h9a2.25 2.25 0 012.25 2.25v9a2.25 2.25 0 01-2.25 2.25h-9a2.25 2.25 0 01-2.25-2.25v-9z" />
                                                    </svg>
                                                ) : (
                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
                                                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                                                    </svg>
                                                )}
                                            </button>
                                        </div>

                                        {/* Separator */}
                                        <div className="w-px h-8 bg-white/10" />

                                        {/* Screen Share */}
                                        <button
                                            onClick={toggleScreenShare}
                                            disabled={connectionStatus !== 'connected'}
                                            className={`w-14 h-14 rounded-full flex items-center justify-center transition-all ${
                                                isScreenSharing 
                                                    ? 'bg-green-500/20 text-green-400 animate-pulse ring-1 ring-green-500/50' 
                                                    : 'bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700'
                                            } disabled:opacity-40 disabled:cursor-not-allowed`}
                                            title={isScreenSharing ? "Stop Sharing" : "Share Screen"}
                                        >
                                            {isScreenSharing ? (
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                </svg>
                                            ) : (
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m-9-12V15a2.25 2.25 0 002.25 2.25h9.5A2.25 2.25 0 0019 15V5.25m-9-3h9.5A2.25 2.25 0 0121.75 5.25v9a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 14.25V5.25A2.25 2.25 0 015.25 3h9.5z" />
                                                </svg>
                                            )}
                                        </button>
                                    </div>
                                    
                                    {/* Audio Level Visualizer (Subtle background when recording) */}
                                    {isRecording && (
                                        <div 
                                            className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-red-500/20 to-transparent pointer-events-none z-0 transition-all duration-75 ease-out"
                                            style={{ height: `${Math.max(128, audioLevel * 500)}px` }} 
                                        />
                                    )}
                                </div>
                            )}

                        </div>
                    </div>
                </section>
            </main>

            {/* Command Bar Removed */}

            {/* Hidden elements for screen capturing */}
            <video ref={screenVideoRef} className="hidden" muted playsInline />
            <canvas ref={screenCanvasRef} className="hidden" />
        </div>
    );
}
