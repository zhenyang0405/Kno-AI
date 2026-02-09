import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { type User } from 'firebase/auth';
import AddKnowledgeModal from '../components/AddKnowledgeModal';
import type { KnowledgeItem } from '../types';

interface LandingPageProps {
    user: User | null;
    knowledgeList: KnowledgeItem[];
    onAddKnowledge: (name: string, description: string) => void;
}

function LandingPage({ user, knowledgeList, onAddKnowledge }: LandingPageProps) {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const navigate = useNavigate();

    const handleStartOnboarding = () => {
        if (user) {
            navigate(`/onboarding?uid=${user.uid}`);
        }
    };

    return (
        <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 p-6 md:p-12 transition-colors duration-300">
            {/* Header */}
            <header className="mb-12 flex items-center justify-between">
                <h1 className="text-4xl font-black tracking-tight text-zinc-900 dark:text-zinc-50">
                    Kno - AI Educate
                    <span className="ml-2 inline-block h-3 w-3 animate-pulse rounded-full bg-blue-600"></span>
                </h1>
            </header>

            {/* AI Personalization Section */}
            <section className="mb-12 overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-blue-600 to-indigo-700 p-8 md:p-12 text-white shadow-2xl shadow-blue-500/20 ring-4 ring-white/10 dark:ring-white/5">
                <div className="relative z-10 flex flex-col items-start space-y-6 md:max-w-3xl">
                    <div className="inline-flex items-center space-x-2 rounded-full bg-white/20 px-4 py-1.5 text-xs font-black uppercase tracking-widest backdrop-blur-md">
                        <span className="h-2 w-2 animate-ping rounded-full bg-white"></span>
                        <span>Personalize Your Journey</span>
                    </div>
                    <h2 className="text-4xl font-black tracking-tight md:text-5xl">
                        Let's build your Learning Profile.
                    </h2>
                    <p className="text-lg font-medium text-blue-100 leading-relaxed">
                        Have a quick conversation with our agent so we can understand your learning style, 
                        goals, and preferences. Get a truly customized educational experience.
                    </p>
                    <button
                        onClick={handleStartOnboarding}
                        className="group flex items-center space-x-3 rounded-2xl bg-white px-8 py-4 font-black text-blue-600 transition-all hover:scale-105 active:scale-95 shadow-xl shadow-black/10"
                    >
                        <span>Start Personal Conversation</span>
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="h-5 w-5 transition-transform group-hover:translate-x-1">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 8.25L21 12m0 0l-3.75 3.75M21 12H3" />
                        </svg>
                    </button>
                </div>

                {/* Decorative Elements */}
                <div className="absolute right-0 top-0 -mr-16 -mt-16 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
                <div className="absolute bottom-0 left-0 -ml-16 -mb-16 h-64 w-64 rounded-full bg-blue-400/20 blur-3xl" />
            </section>

            {/* Main Content */}
            <main className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {/* Add New Item Box */}
                <button
                    onClick={() => setIsModalOpen(true)}
                    className="group relative flex h-64 flex-col items-center justify-center space-y-4 rounded-3xl border-2 border-dashed border-zinc-300 bg-white/50 p-8 text-center transition-all hover:border-blue-500 hover:bg-blue-50/50 dark:border-zinc-800 dark:bg-zinc-900/50 dark:hover:border-blue-500 dark:hover:bg-blue-900/20"
                >
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-zinc-100 text-zinc-400 transition-colors group-hover:bg-blue-100 group-hover:text-blue-600 dark:bg-zinc-800 dark:group-hover:bg-blue-900/40">
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={2}
                            stroke="currentColor"
                            className="h-8 w-8"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                        </svg>
                    </div>
                    <div>
                        <span className="text-lg font-bold text-zinc-900 dark:text-zinc-100">Add New Knowledge</span>
                        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Share something you want to learn</p>
                    </div>
                </button>

                {/* Knowledge List */}
                {knowledgeList.map((item) => (
                    <div
                        key={item.id}
                        onClick={() => navigate(`/knowledge/${item.id}`)}
                        className="flex h-64 cursor-pointer flex-col justify-between rounded-3xl bg-white p-8 shadow-sm ring-1 ring-zinc-200 transition-all hover:shadow-xl hover:ring-blue-500/30 dark:bg-zinc-900 dark:ring-zinc-800 dark:hover:ring-blue-500/30 active:scale-[0.98]"
                    >
                        <div>
                            <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{item.name}</h3>
                            <p className="mt-3 line-clamp-4 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                                {item.description}
                            </p>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold uppercase tracking-widest text-zinc-400">Knowledge</span>
                            <div className="text-zinc-400 group-hover:text-blue-600 dark:text-zinc-600 dark:group-hover:text-blue-400 transition-colors">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-5 w-5">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 8.25L21 12m0 0l-3.75 3.75M21 12H3" />
                                </svg>
                            </div>
                        </div>
                    </div>
                ))}
            </main>

            {/* Modal */}
            <AddKnowledgeModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onSave={onAddKnowledge}
            />
        </div>
    );
}

export default LandingPage;
