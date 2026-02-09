import { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
    role: 'user' | 'agent';
    content: string;
    timestamp: Date;
}

const BASE_URL = 'https://onboarding-agent-460848097230.us-east1.run.app';
// const BASE_URL = 'http://localhost:8001';

export default function OnboardingPage() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const uid = searchParams.get('uid');
    
    const [messages, setMessages] = useState<Message[]>([]);
    const [initialLoading, setInitialLoading] = useState(true);

    // Fetch personalized welcome message
    useEffect(() => {
        const fetchWelcome = async () => {
            if (!uid) return;
            
            try {
                const response = await fetch(`${BASE_URL}/chat/welcome?uid=${uid}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ uid })  // redundant but safe
                });
                
                if (response.ok) {
                    const data = await response.json();
                    setMessages([{
                        role: 'agent',
                        content: data.response,
                        timestamp: new Date()
                    }]);
                } else {
                    // Fallback if API fails
                    setMessages([{
                        role: 'agent',
                        content: "Hello! I'm here to help you build your personalized learning profile. To get started, what topics are you most interested in?",
                        timestamp: new Date()
                    }]);
                }
            } catch (err) {
                console.error("Failed to fetch welcome:", err);
                setMessages([{
                    role: 'agent',
                    content: "Hello! I'm ready to learn about your preferences. What would you like to learn?",
                    timestamp: new Date()
                }]);
            } finally {
                setInitialLoading(false);
            }
        };

        fetchWelcome();
    }, [uid]);
    const [input, setInput] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping]);

    const handleSend = async () => {
        if (!input.trim() || !uid) return;

        const userMessage: Message = {
            role: 'user',
            content: input.trim(),
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsTyping(true);

        try {
            const response = await fetch(`${BASE_URL}/chat?uid=${uid}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: userMessage.content }),
            });

            if (!response.ok) {
                throw new Error('Failed to get response from agent');
            }

            const data = await response.json();
            
            const agentMessage: Message = {
                role: 'agent',
                content: data.response || "I'm sorry, I couldn't process that.",
                timestamp: new Date()
            };
            setMessages(prev => [...prev, agentMessage]);
        } catch (error) {
            console.error('Error calling agent:', error);
            const errorMessage: Message = {
                role: 'agent',
                content: "I'm having a bit of trouble connecting to my brain right now. Please try again in a moment!",
                timestamp: new Date()
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsTyping(false);
        }
    };

    return (
        <div className="flex h-screen flex-col bg-zinc-50 dark:bg-zinc-950 font-sans selection:bg-blue-100 selection:text-blue-700">
            {/* Header */}
            <header className="flex items-center justify-between border-b border-zinc-200 bg-white/80 px-6 py-4 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-900/80">
                <div className="flex items-center space-x-4">
                    <button
                        onClick={() => navigate('/')}
                        className="rounded-full p-2 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="h-5 w-5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                        </svg>
                    </button>
                    <div>
                        <h1 className="text-lg font-black tracking-tight text-zinc-900 dark:text-zinc-50">Personal Concierge</h1>
                        <div className="flex items-center space-x-1.5 text-xs font-bold text-green-500 uppercase tracking-widest">
                            <span className="relative flex h-2 w-2">
                                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75"></span>
                                <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500"></span>
                            </span>
                            <span>Online</span>
                        </div>
                    </div>
                </div>
                <div className="hidden sm:block rounded-full bg-zinc-100 px-4 py-1.5 text-[10px] font-black uppercase tracking-widest text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                    UID: {uid?.slice(0, 8)}...
                </div>
            </header>

            {/* Chat Area */}
            <main className="flex-1 overflow-y-auto p-4 md:p-8">
                <div className="mx-auto max-w-5xl space-y-8">
                    {messages.map((message, index) => (
                        <div
                            key={index}
                            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-4 duration-500`}
                        >
                            <div
                                className={`group relative max-w-[85%] rounded-[2rem] p-6 shadow-sm transition-all hover:shadow-md ${
                                    message.role === 'user'
                                        ? 'bg-blue-600 text-white rounded-br-none'
                                        : 'bg-white border border-zinc-100 text-zinc-800 rounded-bl-none dark:bg-zinc-900 dark:border-zinc-800 dark:text-zinc-100'
                                }`}
                            >
                                <div className={`prose prose-lg dark:prose-invert max-w-none ${message.role === 'user' ? 'prose-p:text-white prose-headings:text-white prose-strong:text-white' : 'prose-p:text-zinc-800 dark:prose-p:text-zinc-100 prose-headings:text-zinc-900 dark:prose-headings:text-zinc-50 prose-strong:text-zinc-900 dark:prose-strong:text-zinc-50'}`}>
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {message.content}
                                    </ReactMarkdown>
                                </div>
                                <span className={`mt-2 block text-[10px] font-bold uppercase tracking-wider opacity-50 ${message.role === 'user' ? 'text-right' : 'text-left'}`}>
                                    {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            </div>
                        </div>
                    ))}
                    {initialLoading && (
                        <div className="flex justify-start animate-in fade-in duration-300">
                             <div className="bg-white dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800 rounded-[2rem] rounded-bl-none p-4 px-6 shadow-sm">
                                <div className="flex space-x-1.5">
                                    <div className="h-2 w-2 animate-bounce rounded-full bg-blue-600 [animation-delay:-0.3s]"></div>
                                    <div className="h-2 w-2 animate-bounce rounded-full bg-blue-600 [animation-delay:-0.15s]"></div>
                                    <div className="h-2 w-2 animate-bounce rounded-full bg-blue-600"></div>
                                </div>
                            </div>
                        </div>
                    )}
                    {isTyping && !initialLoading && (
                        <div className="flex justify-start">
                            <div className="bg-white dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800 rounded-[2rem] rounded-bl-none p-4 px-6 shadow-sm">
                                <div className="flex space-x-1.5">
                                    <div className="h-2 w-2 animate-bounce rounded-full bg-blue-600 [animation-delay:-0.3s]"></div>
                                    <div className="h-2 w-2 animate-bounce rounded-full bg-blue-600 [animation-delay:-0.15s]"></div>
                                    <div className="h-2 w-2 animate-bounce rounded-full bg-blue-600"></div>
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} className="h-4" />
                </div>
            </main>

            {/* Input Area */}
            <footer className="sticky bottom-0 border-t border-zinc-200 bg-white/80 p-6 backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-950/80">
                <div className="mx-auto max-w-5xl">
                    <div className="relative flex items-center shadow-2xl shadow-blue-900/5 rounded-3xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 transition-all">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                            placeholder="Type your message here..."
                            className="w-full bg-transparent border-none p-5 pl-6 pr-16 text-lg font-medium text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400"
                        />
                        <button
                            onClick={handleSend}
                            disabled={!input.trim()}
                            className="absolute right-3 p-3 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105 active:scale-95 shadow-lg shadow-blue-600/20"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                                <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
                            </svg>
                        </button>
                    </div>
                    <p className="mt-4 text-center text-[10px] font-bold uppercase tracking-widest text-zinc-400 dark:text-zinc-600">
                        Agent is listening to your preferences
                    </p>
                </div>
            </footer>
        </div>
    );
}
