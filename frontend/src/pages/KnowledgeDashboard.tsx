import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getKnowledgeDetails, getKnowledgeDocuments, uploadDocument, deleteDocument } from '../services/api';
import type { KnowledgeItem, DocumentItem } from '../types';

interface KnowledgeDashboardProps {
    knowledgeList: KnowledgeItem[];
}

function KnowledgeDashboard({ knowledgeList }: KnowledgeDashboardProps) {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [documents, setDocuments] = useState<DocumentItem[]>([]);
    const [itemDetails, setItemDetails] = useState<KnowledgeItem | null>(null);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [pendingFiles, setPendingFiles] = useState<File[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const item = knowledgeList.find((k) => k.id === id);

    // Fetch knowledge details and documents
    const fetchData = async () => {
        if (!id) return;

        try {
            const [details, docs] = await Promise.all([
                getKnowledgeDetails(id),
                getKnowledgeDocuments(id)
            ]);
            setItemDetails(details);
            setDocuments(docs);
        } catch (error) {
            console.error("Error fetching knowledge data:", error);
        }
    };

    useEffect(() => {
        if (!id) return;
        fetchData();
    }, [id]);

    if (!item && !itemDetails) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 p-6 dark:bg-zinc-950">
                <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Knowledge not found</h2>
                <button
                    onClick={() => navigate('/')}
                    className="mt-4 rounded-lg bg-blue-600 px-6 py-2 text-white hover:bg-blue-700 transition-colors"
                >
                    Go Back Home
                </button>
            </div>
        );
    }

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        const fileList = Array.from(files);
        setPendingFiles(prev => [...prev, ...fileList]);

        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const removePendingFile = (index: number) => {
        setPendingFiles(prev => prev.filter((_, i) => i !== index));
    };

    const handleAdditionalDocumentsUpload = async (topicId: string) => {
        if (pendingFiles.length === 0 || !id) return;

        setUploading(true);
        setUploadError(null);

        try {
            for (const file of pendingFiles) {
                await uploadDocument(id, file, topicId);
            }
            setPendingFiles([]);
            // Refresh data after upload
            await fetchData();
        } catch (error) {
            console.error("Upload failed:", error);
            setUploadError(error instanceof Error ? error.message : "Failed to upload files");
        } finally {
            setUploading(false);
        }
    };

    const triggerFileInput = () => {
        fileInputRef.current?.click();
    };

    const handleDeleteDocument = async (docId: string) => {
        if (!id || !window.confirm('Are you sure you want to delete this document?')) return;

        try {
            await deleteDocument(id, docId);
            // Refresh data after delete
            await fetchData();
        } catch (error) {
            console.error("Delete failed:", error);
            alert(error instanceof Error ? error.message : "Failed to delete document");
        }
    };

    return (
        <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 p-6 md:p-12 transition-colors duration-300">
            {/* Header */}
            <header className="mb-12">
                <button
                    onClick={() => navigate('/')}
                    className="group mb-6 flex items-center space-x-2 text-sm font-medium text-zinc-500 hover:text-blue-600 dark:text-zinc-400 dark:hover:text-blue-400 transition-colors"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-4 w-4 transition-transform group-hover:-translate-x-1">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                    </svg>
                    <span>Back to Library</span>
                </button>

                <h1 className="text-4xl font-black tracking-tight text-zinc-900 dark:text-zinc-50">
                    {itemDetails?.name || item?.name}
                </h1>
                {/* <p className="mt-4 max-w-2xl text-lg text-zinc-600 dark:text-zinc-400 leading-relaxed">
                    {itemDetails?.description || item?.description}
                </p> */}
            </header>

            <main className="flex flex-col lg:flex-row gap-8">
                <div className="flex-1 space-y-8">
                    {/* Overview Section */}
                    <section className="rounded-3xl bg-white p-8 shadow-sm ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800">
                        <div className="flex items-start justify-between mb-4">
                            <div>
                                <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-1">Course Overview</h2>
                                <p className="text-sm text-zinc-500 dark:text-zinc-400">Get started with your learning journey</p>
                            </div>
                            <button
                                onClick={() => navigate(`/knowledge/${id}/topic/all/study`)}
                                className="px-6 py-2.5 bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-zinc-50 dark:text-zinc-900 text-sm font-bold rounded-xl transition-all shadow-lg hover:scale-105 active:scale-95 flex items-center space-x-2"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41c-.076-2.126-.243-4.245-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A5.905 5.905 0 018 3.993a5.905 5.905 0 018 3.993 5.903 5.903 0 013.918 5.338m-15.482 0c.253-1.042.597-2.056 1.026-3.033M16.5 19.5v-3.75a.75.75 0 00-.75-.75h-3.75" />
                                </svg>
                                <span>Start Learning</span>
                            </button>
                        </div>
                        <div className="prose prose-zinc dark:prose-invert max-w-none">
                            <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed">
                                {itemDetails?.overview || itemDetails?.description || "Start uploading materials to build your knowledge base"}
                            </p>
                        </div>
                    </section>

                    {/* Topics Section */}
                    <section className="rounded-3xl bg-white p-8 shadow-sm ring-1 ring-zinc-200 dark:bg-zinc-900 dark:ring-zinc-800">
                        <div className="flex items-center justify-between mb-8">
                            <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">Study Materials</h2>
                            <span className="px-3 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                                {documents.length} Documents
                            </span>
                        </div>

                        {/* Documents Grid */}
                        {documents.length > 0 ? (
                            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6 mb-12">
                                {documents.map((doc) => (
                                    <div
                                        key={doc.id}
                                        onClick={() => navigate(`/knowledge/${id}/topic/all/study?docId=${doc.id}`)}
                                        className="group/doc relative flex flex-col p-5 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-800 hover:border-blue-500/30 hover:shadow-lg hover:shadow-blue-500/5 transition-all cursor-pointer aspect-[2/1] justify-between"
                                    >
                                        <div className="flex flex-col items-center text-center space-y-3 pt-2">
                                            <div className="p-3 bg-white dark:bg-zinc-900 rounded-xl text-zinc-400 group-hover/doc:text-blue-600 group-hover/doc:scale-110 transition-all shadow-sm">
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-6 w-6">
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                                                </svg>
                                            </div>
                                            <div>
                                                <p className="text-sm font-bold text-zinc-900 dark:text-zinc-100 line-clamp-2 leading-tight px-2">
                                                    {doc.filename}
                                                </p>
                                                <p className="text-xs text-zinc-500 mt-1.5">
                                                    {doc.uploadedAt ? new Date(typeof doc.uploadedAt === 'object' && 'seconds' in doc.uploadedAt ? doc.uploadedAt.seconds * 1000 : doc.uploadedAt).toLocaleDateString() : 'No date'}
                                                </p>
                                            </div>
                                        </div>

                                        {/* Hover Actions */}
                                        <div className="absolute top-3 right-3 flex space-x-1 opacity-0 group-hover/doc:opacity-100 transition-opacity translate-y-2 group-hover/doc:translate-y-0 duration-300">

                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDeleteDocument(doc.id);
                                                }}
                                                className="p-1.5 bg-white dark:bg-zinc-900 rounded-lg text-zinc-400 hover:text-red-600 shadow-sm border border-zinc-100 dark:border-zinc-800"
                                                title="Delete"
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-4 w-4">
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                                </svg>
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-12 mb-8">
                                <div className="inline-flex items-center justify-center p-4 bg-zinc-50 dark:bg-zinc-800 rounded-full mb-4">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-8 w-8 text-zinc-400">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                                    </svg>
                                </div>
                                <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-100">No materials yet</h3>
                                <p className="text-zinc-500 text-sm mt-1">Upload documents to get started</p>
                            </div>
                        )}

                        {/* Separate Actions Section (Upload) */}
                        <div className="border-t border-zinc-200 dark:border-zinc-800 pt-8">
                            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 uppercase tracking-wider mb-4">Add Content</h3>
                            
                            {pendingFiles.length > 0 ? (
                                <div className="bg-zinc-50 dark:bg-zinc-900/50 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800">
                                    <div className="flex items-center justify-between mb-4">
                                        <span className="text-xs font-bold text-zinc-500 uppercase">Selected Files ({pendingFiles.length})</span>
                                        <button
                                            onClick={triggerFileInput}
                                            className="text-xs font-bold text-blue-600 hover:text-blue-700 dark:text-blue-400 transition-colors"
                                        >
                                            + Add More
                                        </button>
                                    </div>

                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
                                        {pendingFiles.map((file, idx) => (
                                            <div key={idx} className="flex items-center justify-between bg-white dark:bg-zinc-800 px-4 py-3 rounded-xl border border-zinc-200 dark:border-zinc-700 text-sm font-medium text-zinc-700 dark:text-zinc-300 shadow-sm relative group">
                                                <div className="flex items-center space-x-3 truncate">
                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 text-zinc-400">
                                                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                                                    </svg>
                                                    <span className="truncate">{file.name}</span>
                                                </div>
                                                <button 
                                                    onClick={() => removePendingFile(idx)} 
                                                    className="p-1 bg-zinc-100 dark:bg-zinc-700 rounded-full text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 transition-all opacity-0 group-hover:opacity-100"
                                                >
                                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                                                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                                    </svg>
                                                </button>
                                            </div>
                                        ))}
                                    </div>

                                    <button
                                        onClick={() => handleAdditionalDocumentsUpload('')}
                                        disabled={uploading}
                                        className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-blue-500/20 disabled:opacity-50 flex items-center justify-center space-x-2 active:scale-[0.98]"
                                    >
                                        {uploading ? (
                                            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                            </svg>
                                        ) : (
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                                            </svg>
                                        )}
                                        <span>{uploading ? 'Uploading Files...' : 'Upload Selected Files'}</span>
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={triggerFileInput}
                                    className="group flex flex-col items-center justify-center w-full py-12 border-2 border-dashed border-zinc-200 dark:border-zinc-800 rounded-2xl cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/30 transition-all"
                                >
                                    <div className="p-4 rounded-full bg-blue-50 dark:bg-blue-900/10 text-blue-500 group-hover:scale-110 transition-transform mb-4">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-8 h-8">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                                        </svg>
                                    </div>
                                    <h4 className="text-zinc-900 dark:text-zinc-100 font-bold">Add More Materials</h4>
                                    <p className="text-zinc-500 text-sm mt-1">Click to select files from your computer</p>
                                </button>
                            )}

                            {uploadError && (
                                <div className="mt-6 rounded-xl bg-red-50 p-4 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400 border border-red-100 dark:border-red-900/30 flex items-center space-x-2">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                                    </svg>
                                    <span>{uploadError}</span>
                                </div>
                            )}
                        </div>
                    </section>
                </div>
            </main>
            
            <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                multiple
                className="hidden"
            />
        </div>
    );
}

export default KnowledgeDashboard;
