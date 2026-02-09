import { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { auth } from '../firebase';
import { getKnowledgeDetails, getKnowledgeDocuments } from '../services/api';
import type { KnowledgeItem, Topic, DocumentItem } from '../types';
import ActiveLearningWorkspace from '../components/ActiveLearningWorkspace';
import { createStudySession, getUserId } from '../services/activeLearning';



interface StudySessionProps {
    knowledgeList: KnowledgeItem[];
}

type StudyFlow = 'pre-assessment' | 'active-learning' | 'post-assessment';

export default function StudySession({ knowledgeList }: StudySessionProps) {
    const { id, topicId } = useParams<{ id: string; topicId: string }>();
    const navigate = useNavigate();
    const [currentFlow, setCurrentFlow] = useState<StudyFlow>('pre-assessment');
    const [itemDetails, setItemDetails] = useState<KnowledgeItem | null>(null);
    const [documents, setDocuments] = useState<DocumentItem[]>([]);
    const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
    const [searchParams] = useSearchParams();
    
    // Auto-select document from query param
    useEffect(() => {
        const docIdFromUrl = searchParams.get('docId');
        if (docIdFromUrl) {
            setSelectedDocId(docIdFromUrl);
        }
    }, [searchParams]);
    const [isGenerating, setIsGenerating] = useState(false);

    const [questions, setQuestions] = useState<any[]>([]);
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
    const [userAnswers, setUserAnswers] = useState<Record<number, string>>({});
    
    // Separate IDs for pre and post assessments
    const [preAssessmentId, setPreAssessmentId] = useState<number | null>(null);
    const [postAssessmentId, setPostAssessmentId] = useState<number | null>(null);
    
    // Derived assessmentId based on flow
    const assessmentId = currentFlow === 'post-assessment' ? postAssessmentId : preAssessmentId;

    const [quizStarted, setQuizStarted] = useState(false);
    const [assessmentResults, setAssessmentResults] = useState<any | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isActiveLearningStarted, setIsActiveLearningStarted] = useState(false);
    const [studySessionId, setStudySessionId] = useState<number | null>(null);
    const [userId, setUserId] = useState<number | null>(null);

    const PRE_ASSESSMENT_API_URL = 'https://pre-assessment-agent-460848097230.us-east1.run.app/api/pre-assessment';
    const POST_ASSESSMENT_API_URL = 'https://post-assessment-agent-460848097230.us-east1.run.app/api/post-assessment';

    // const PRE_ASSESSMENT_API_URL = 'http://localhost:8002/api/pre-assessment';
    // const POST_ASSESSMENT_API_URL = 'http://localhost:8001/api/post-assessment';

    const currentApiUrl = currentFlow === 'post-assessment' ? POST_ASSESSMENT_API_URL : PRE_ASSESSMENT_API_URL;




    const itemFromList = knowledgeList.find((k) => k.id === id);
    const item = itemDetails || itemFromList;

    // Fetch knowledge details and documents via API
    useEffect(() => {
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
                console.error("Error fetching study session data:", error);
            }
        };
        
        fetchData();
    }, [id]);

    // Fetch userId from Firebase UID
    useEffect(() => {
        const fetchUserId = async () => {
            if (!auth.currentUser) return;
            
            try {
                const firebaseUid = auth.currentUser.uid;
                    
                const dbUserId = await getUserId(firebaseUid);
                setUserId(dbUserId);
                console.log('Mapped Firebase UID to database user_id:', dbUserId);
            } catch (error) {
                console.error('Failed to fetch user ID:', error);
            }
        };
        
        fetchUserId();
    }, [auth.currentUser]);


    // Resolve topics - removed syllabus support
    const resolvedTopics: Topic[] = (item?.topics || []);

    const topic = resolvedTopics.find((t) => t.id === topicId);
    const topicIndex = resolvedTopics.findIndex(t => t.id === topicId);

    // Document filtering - simplified without syllabus
    const topicDocs = topicId === 'all' ? documents : documents.filter(doc => doc.topicId === topicId);
    const selectedDoc = topicDocs.find(d => d.id === selectedDocId);


    // Auto-select if only one document exists
    useEffect(() => {
        if (topicDocs.length === 1 && !selectedDocId) {
            setSelectedDocId(topicDocs[0].id);
        }
    }, [topicDocs, selectedDocId]);

    const steps = [
        { id: 'pre-assessment', label: 'Pre-Assessment' },
        { id: 'active-learning', label: 'Active Learning' },
        { id: 'post-assessment', label: 'Post-Assessment' },
    ];

    const currentStepIndex = steps.findIndex(s => s.id === currentFlow);

    const handleStartPreAssessment = async () => {
        if (!selectedDoc || !auth.currentUser || !userId) {
            console.error('Missing required data: selectedDoc, auth, or userId');
            return;
        }

        // Ensure study session exists
        let currentSessionId = studySessionId;
        if (!currentSessionId) {
            try {
                const doc = topicDocs.find(d => d.id === selectedDocId);
                const material_id = parseInt(doc!.id);
                const sessionRes = await createStudySession({
                    user_id: userId,
                    material_id
                });
                setStudySessionId(sessionRes.session.id);
                currentSessionId = sessionRes.session.id;
                console.log('Study session created (post-assessment):', currentSessionId);
            } catch (error) {
                console.error('Failed to create study session:', error);
                alert('Could not start post-assessment. Please try again.');
                return;
            }
        }

        setIsGenerating(true);
        try {
            // 1. Generate Questions
            const material_id = parseInt(selectedDoc.id);
            const storage_bucket = selectedDoc.storageBucket || 'ai-educate-storage'; // Fallback if not present

            const generateRes = await fetch(`${currentApiUrl}/generate-questions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    material_id,
                    storage_path: selectedDoc.storagePath,
                    storage_bucket,
                    session_id: String(currentSessionId),
                    user_id: userId,
                })
            });
            const generateData = await generateRes.json();

            // Handle existing completed assessment
            if (generateData.assessment_status === 'completed') {
                const sessionRes = await createStudySession({
                    user_id: userId,
                    material_id,
                    pre_assessment_id: generateData.assessment_id
                });
                setStudySessionId(sessionRes.session.id);
                setPreAssessmentId(generateData.assessment_id);
                setAssessmentResults(generateData);
                setQuizStarted(false);
                setIsGenerating(false);
                return;
            }

            // 3. Start Assessment
            const startRes = await fetch(`${currentApiUrl}/start-assessment`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    material_id: material_id,
                    session_id: currentSessionId
                })
            });
            const { assessment_id } = await startRes.json();
            setPreAssessmentId(assessment_id);

            // 4. Create Study Session
            const sessionRes = await createStudySession({
                user_id: userId,
                material_id,
                pre_assessment_id: assessment_id
            });
            setStudySessionId(sessionRes.session.id);
            console.log('Study session created:', sessionRes.session.id);

            // 5. Fetch Questions
            const qRes = await fetch(`${currentApiUrl}/questions/${material_id}`);
            const { questions } = await qRes.json();
            
            setQuestions(questions);
            // Only show questions if we are not completed (which is handled above, but good to be explicit)
            setQuizStarted(true);
        } catch (error) {
            console.error('Failed to start assessment:', error);
            alert('Something went wrong while preparing your assessment. Please try again.');
        } finally {
            setIsGenerating(false);
        }
    };

    const handleStartPostAssessment = async () => {
        if (!selectedDoc || !auth.currentUser || !userId) {
            console.error('Missing required data: selectedDoc, auth, or userId');
            return;
        }

        // Ensure study session exists
        let currentSessionId = studySessionId;
        if (!currentSessionId) {
            try {
                const doc = topicDocs.find(d => d.id === selectedDocId);
                const material_id = parseInt(doc!.id);
                const sessionRes = await createStudySession({
                    user_id: userId,
                    material_id
                });
                setStudySessionId(sessionRes.session.id);
                currentSessionId = sessionRes.session.id;
                console.log('Study session created (post-assessment):', currentSessionId);
            } catch (error) {
                console.error('Failed to create study session:', error);
                alert('Could not start post-assessment. Please try again.');
                return;
            }
        }

        setIsGenerating(true);
        try {
            // 1. Generate Questions
            const material_id = parseInt(selectedDoc.id);
            const storage_bucket = selectedDoc.storageBucket || 'ai-educate-storage';

            const generateRes = await fetch(`${POST_ASSESSMENT_API_URL}/generate-questions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    material_id,
                    storage_path: selectedDoc.storagePath,
                    storage_bucket,
                    session_id: String(currentSessionId),
                    user_id: userId,
                })
            });
            const generateData = await generateRes.json();

            // Handle existing completed assessment
            if (generateData.assessment_status === 'completed') {
                setPostAssessmentId(generateData.assessment_id);
                setAssessmentResults(generateData);
                setIsGenerating(false);
                return;
            }

            // 3. Start Assessment
            const startRes = await fetch(`${POST_ASSESSMENT_API_URL}/start-assessment`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    material_id: material_id,
                    study_session_id: currentSessionId
                })
            });
            const { assessment_id } = await startRes.json();
            setPostAssessmentId(assessment_id);

            // 5. Fetch Questions
            const qRes = await fetch(`${POST_ASSESSMENT_API_URL}/questions/${material_id}`);
            const { questions } = await qRes.json();
            
            setQuestions(questions);
            setQuizStarted(true);
        } catch (error) {
            console.error('Failed to start post-assessment:', error);
            alert('Something went wrong while preparing your post-assessment. Please try again.');
        } finally {
            setIsGenerating(false);
        }
    };

    const handleSaveAnswer = async (questionId: number, answer: string) => {
        if (!assessmentId) return;

        setUserAnswers(prev => ({ ...prev, [questionId]: answer }));
        
        try {
            await fetch(`${currentApiUrl}/save-answer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    assessment_id: assessmentId,
                    question_id: questionId,
                    user_answer: answer
                })
            });
        } catch (error) {
            console.error('Failed to save answer:', error);
        }
    };

    const handleFinishAssessment = async () => {
        if (!assessmentId) return;
        setIsSubmitting(true);
        try {
            const res = await fetch(`${currentApiUrl}/mark-assessment`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    user_id: userId, 
                    session_id: String(studySessionId), 
                    assessment_id: assessmentId 
                })
            });
            const data = await res.json();
            setAssessmentResults(data);
            setQuizStarted(false);
        } catch (error) {
            console.error('Failed to mark assessment:', error);
        } finally {
            setIsSubmitting(false);
        }
    };

    const renderGeneratingUI = () => (
        <div className="text-center space-y-8 animate-in fade-in zoom-in-95 duration-700">
            <div className="relative">
                <div className="h-32 w-32 mx-auto relative flex items-center justify-center">
                    <div className="absolute inset-0 rounded-full border-4 border-blue-100 dark:border-blue-900/20" />
                    <div className="absolute inset-0 rounded-full border-4 border-t-blue-600 animate-spin" />
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-12 h-12 text-blue-600 animate-pulse">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
                    </svg>
                </div>
            </div>
            <div className="space-y-3">
                <h2 className="text-3xl font-black text-zinc-900 dark:text-zinc-50">Generating questions...</h2>
                <p className="text-zinc-500 dark:text-zinc-400 max-w-sm mx-auto leading-relaxed italic">
                    "Our AI specialist is reading your document to craft the perfect assessment for your level."
                </p>
                <div className="flex items-center justify-center gap-2 text-blue-600 font-bold text-xs uppercase tracking-widest pt-4">
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-600 animate-bounce [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-600 animate-bounce [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-600 animate-bounce" />
                </div>
            </div>
        </div>
    );

    const renderQuizUI = () => {
        const currentQuestion = questions[currentQuestionIndex];
        if (!currentQuestion) return null;

        return (
            <div className="w-full max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
                <div className="flex items-center justify-between mb-8">
                    <div className="space-y-1">
                        <span className="text-xs font-black text-blue-600 dark:text-blue-400 uppercase tracking-widest">
                            Question {currentQuestionIndex + 1} of {questions.length}
                        </span>
                        <div className="h-1.5 w-48 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                            <div 
                                className="h-full bg-blue-600 transition-all duration-500" 
                                style={{ width: `${((currentQuestionIndex + 1) / questions.length) * 100}%` }}
                            />
                        </div>
                    </div>
                    <div className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-wider border ${
                        currentQuestion.difficulty === 'easy' ? 'bg-emerald-50 text-emerald-600 border-emerald-100 dark:bg-emerald-950/20 dark:border-emerald-900/30' :
                        currentQuestion.difficulty === 'medium' ? 'bg-amber-50 text-amber-600 border-amber-100 dark:bg-amber-950/20 dark:border-amber-900/30' :
                        'bg-rose-50 text-rose-600 border-rose-100 dark:bg-rose-950/20 dark:border-rose-900/30'
                    }`}>
                        {currentQuestion.difficulty}
                    </div>
                </div>

                <h3 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50 leading-tight">
                    {currentQuestion.question_text}
                </h3>

                <div className="grid grid-cols-1 gap-3 pt-4">
                    {Object.entries(currentQuestion.options).map(([key, value]) => (
                        <button
                            key={key}
                            onClick={() => handleSaveAnswer(currentQuestion.id, key)}
                            className={`
                                flex items-center p-5 rounded-2xl border transition-all text-left
                                ${userAnswers[currentQuestion.id] === key 
                                    ? 'bg-blue-600 border-blue-600 text-white shadow-lg shadow-blue-500/20' 
                                    : 'bg-white dark:bg-zinc-900 border-zinc-100 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:border-zinc-300 dark:hover:border-zinc-700'}
                            `}
                        >
                            <span className={`
                                h-8 w-8 flex items-center justify-center rounded-xl font-black mr-4 text-sm
                                ${userAnswers[currentQuestion.id] === key ? 'bg-white/20 text-white' : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400'}
                            `}>
                                {key}
                            </span>
                            <span className="font-medium">{value as string}</span>
                        </button>
                    ))}
                </div>

                <div className="flex items-center justify-between pt-12 border-t border-zinc-100 dark:border-zinc-800">
                    <button
                        disabled={currentQuestionIndex === 0}
                        onClick={() => setCurrentQuestionIndex(prev => prev - 1)}
                        className="p-3 disabled:opacity-0 text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-6 h-6">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                        </svg>
                    </button>

                    {currentQuestionIndex < questions.length - 1 ? (
                        <button
                            disabled={!userAnswers[currentQuestion.id]}
                            onClick={() => setCurrentQuestionIndex(prev => prev + 1)}
                            className="bg-zinc-900 dark:bg-zinc-100 text-zinc-50 dark:text-zinc-900 px-8 py-3 rounded-2xl font-bold shadow-xl shadow-zinc-200 dark:shadow-none hover:scale-105 transition-all active:scale-95 disabled:opacity-50 disabled:hover:scale-100"
                        >
                            Next Question
                        </button>
                    ) : (
                        <button
                            disabled={!userAnswers[currentQuestion.id] || isSubmitting}
                            onClick={handleFinishAssessment}
                            className="bg-blue-600 text-white px-10 py-3 rounded-2xl font-bold shadow-xl shadow-blue-500/20 hover:scale-105 transition-all active:scale-95 disabled:opacity-50"
                        >
                            {isSubmitting ? 'Submitting...' : 'Finish Assessment'}
                        </button>
                    )}
                </div>
            </div>
        );
    };

    const renderResultsUI = () => {
        if (!assessmentResults) return null;

        return (
            <div className="w-full max-w-4xl mx-auto space-y-10 animate-in fade-in zoom-in-95 duration-500">
                <div className="text-center space-y-4">
                    <div className="inline-flex items-center justify-center h-24 w-24 rounded-full bg-blue-50 dark:bg-blue-900/20 text-blue-600 font-black text-3xl border-4 border-blue-100 dark:border-blue-900/30">
                        {assessmentResults.percentage}%
                    </div>
                    <div>
                        <h2 className="text-3xl font-black text-zinc-900 dark:text-zinc-50">Assessment Complete!</h2>
                        <p className="text-zinc-500 dark:text-zinc-400 uppercase tracking-widest font-black text-xs">
                            Scored {assessmentResults.score} out of {assessmentResults.total_questions}
                        </p>
                    </div>
                </div>

                <div className="bg-white dark:bg-zinc-800/50 p-8 rounded-3xl border border-zinc-100 dark:border-zinc-800 space-y-6">
                    <div className="flex items-center space-x-2 text-blue-600 mb-4">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
                        </svg>
                        <span className="text-sm font-black uppercase tracking-wider">AI feedback</span>
                    </div>

                    {assessmentResults.structured_summary ? (
                        <div className="space-y-8">
                            <div className="prose dark:prose-invert max-w-none">
                                <p className="text-zinc-700 dark:text-zinc-300 font-medium leading-relaxed">
                                    {assessmentResults.structured_summary.overall_performance}
                                </p>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-3">
                                    <h4 className="flex items-center text-sm font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wide">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4 mr-2">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                        Strengths
                                    </h4>
                                    <ul className="space-y-2">
                                        {assessmentResults.structured_summary.strengths.map((item: string, i: number) => (
                                            <li key={i} className="flex items-start text-sm text-zinc-600 dark:text-zinc-400">
                                                <span className="mr-2 mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-emerald-400/50" />
                                                <span>{item}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>

                                <div className="space-y-3">
                                    <h4 className="flex items-center text-sm font-bold text-rose-600 dark:text-rose-400 uppercase tracking-wide">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4 mr-2">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                                        </svg>
                                        Areas for Improvement
                                    </h4>
                                    <ul className="space-y-2">
                                        {assessmentResults.structured_summary.areas_for_improvement.map((item: string, i: number) => (
                                            <li key={i} className="flex items-start text-sm text-zinc-600 dark:text-zinc-400">
                                                <span className="mr-2 mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-rose-400/50" />
                                                <span>{item}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>

                            <div className="bg-blue-50/50 dark:bg-blue-900/10 rounded-2xl p-6 border border-blue-100 dark:border-blue-900/20">
                                <h4 className="flex items-center text-sm font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-4">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4 mr-2">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
                                    </svg>
                                    Recommendations
                                </h4>
                                <ul className="grid grid-cols-1 gap-3">
                                    {assessmentResults.structured_summary.recommendations.map((item: string, i: number) => (
                                        <li key={i} className="flex items-start text-sm text-zinc-700 dark:text-zinc-300">
                                            <span className="mr-2.5 mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-500" />
                                            <span>{item}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    ) : (
                        <p className="text-zinc-700 dark:text-zinc-300 leading-relaxed font-medium">
                            {assessmentResults.summary}
                        </p>
                    )}
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                    <button
                        onClick={async () => {
                            if (!assessmentId) return;
                            try {
                                await fetch(`${currentApiUrl}/update-assessment-status`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        assessment_id: assessmentId,
                                        status: 'in_progress'
                                    })
                                });
                                // Only reset UI if API call succeeded (or we might want to allow retry)
                                setAssessmentResults(null);
                                setQuizStarted(true);
                                setUserAnswers({});
                                setCurrentQuestionIndex(0);
                            } catch (error) {
                                console.error('Failed to update assessment status:', error);
                                alert('Failed to restart quiz. Please try again.');
                            }
                        }}
                        className="w-full sm:w-auto px-8 py-3.5 rounded-2xl border border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 font-bold hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-all"
                    >
                        Retake Quiz
                    </button>
                    
                    {currentFlow === 'post-assessment' ? (
                        <button
                            onClick={() => navigate(`/knowledge/${id}`)}
                            className="w-full sm:w-auto px-10 py-3.5 rounded-2xl bg-zinc-900 dark:bg-zinc-100 text-zinc-50 dark:text-zinc-900 font-bold shadow-lg hover:scale-105 transition-all"
                        >
                            End Study Session
                        </button>
                    ) : (
                        <button
                            onClick={() => {
                                setAssessmentResults(null); 
                                setCurrentFlow('active-learning');
                            }}
                            className="w-full sm:w-auto px-10 py-3.5 rounded-2xl bg-zinc-900 dark:bg-zinc-100 text-zinc-50 dark:text-zinc-900 font-bold shadow-lg hover:scale-105 transition-all"
                        >
                            Continue to Learning →
                        </button>
                    )}
                </div>
            </div>
        );
    };


    const renderFlowContent = () => {
        switch (currentFlow) {
            case 'pre-assessment':
                return (
                    <div className="space-y-8 text-center animate-in fade-in slide-in-from-bottom-4 duration-500 w-full max-w-4xl mx-auto">
                        <div className="inline-flex h-20 w-20 items-center justify-center rounded-3xl bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400 mb-4">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-10 h-10">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
                            </svg>
                        </div>
                        <div>
                            <h2 className="text-3xl font-black text-zinc-900 dark:text-zinc-50 mb-3">Pre-Assessment</h2>
                            <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed mb-8">
                                Select a material to evaluate your current understanding and customize your learning path.
                            </p>
                        </div>

                        <div className="space-y-4 text-left">
                            <label className="text-xs font-bold text-zinc-400 uppercase tracking-widest block px-1">
                                Available Materials
                            </label>
                            <div className="grid grid-cols-1 gap-2">
                                {topicDocs.map((doc) => (
                                    <button
                                        key={doc.id}
                                        onClick={() => setSelectedDocId(doc.id)}
                                        className={`
                                            flex items-center justify-between p-4 rounded-2xl border transition-all
                                            ${selectedDocId === doc.id 
                                                ? 'bg-blue-600 border-blue-600 text-white shadow-lg shadow-blue-500/25 ring-2 ring-blue-600 ring-offset-2 dark:ring-offset-zinc-950' 
                                                : 'bg-white dark:bg-zinc-900 border-zinc-100 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:border-blue-500/50 hover:bg-zinc-50 dark:hover:bg-zinc-800/50'}
                                        `}
                                    >
                                        <div className="flex items-center space-x-3 overflow-hidden">
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={`w-5 h-5 flex-shrink-0 ${selectedDocId === doc.id ? 'text-blue-100' : 'text-zinc-400'}`}>
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                                            </svg>
                                            <span className="font-bold truncate">{doc.filename}</span>
                                        </div>
                                        {selectedDocId === doc.id && (
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor" className="w-5 h-5 text-white">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                                            </svg>
                                        )}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {selectedDocId && (
                            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-8 animate-in fade-in zoom-in-95 duration-300">
                                <button
                                    onClick={async () => {
                                        // Create study session when skipping to learning
                                        try {
                                            const doc = topicDocs.find(d => d.id === selectedDocId);
                                            if (!doc || !userId) {
                                                console.error('Missing document or userId');
                                                return;
                                            }
                                            
                                            const material_id = parseInt(doc.id)
                                            
                                            const sessionRes = await createStudySession({
                                                user_id: userId,
                                                material_id
                                            });
                                            setStudySessionId(sessionRes.session.id);
                                            console.log('Study session created (skip):', sessionRes.session.id);
                                        } catch (error) {
                                            console.error('Failed to create study session:', error);
                                            // Continue to learning even if session creation fails
                                        }
                                        setCurrentFlow('active-learning');
                                    }}
                                    className="w-full sm:w-auto px-8 py-3.5 rounded-2xl border border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 font-bold hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-all active:scale-95"
                                >
                                    Skip to Learning
                                </button>
                                <button
                                    onClick={handleStartPreAssessment}
                                    className="w-full sm:w-auto px-10 py-3.5 rounded-2xl bg-blue-600 text-white font-bold shadow-lg shadow-blue-500/25 hover:bg-blue-700 transition-all active:scale-95"
                                >
                                    Start Assessment
                                </button>
                            </div>
                        )}
                    </div>
                );
            case 'active-learning':
                if (!selectedDoc || !id || !topicId) return null;
                
                if (isActiveLearningStarted) {
                    return (
                        <ActiveLearningWorkspace 
                            selectedDoc={selectedDoc}
                            knowledgeId={id}
                            topicId={topicId}
                            studySessionId={studySessionId}
                            userId={userId}
                            onBack={() => setIsActiveLearningStarted(false)}
                        />
                    );
                }

                return (
                    <div className="space-y-6 text-center animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <div className="inline-flex h-20 w-20 items-center justify-center rounded-3xl bg-indigo-50 text-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400 mb-4">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-10 h-10">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18c-2.305 0-4.408.867-6 2.292m0-14.25v14.25" />
                            </svg>
                        </div>
                        <div>
                            <h2 className="text-3xl font-black text-zinc-900 dark:text-zinc-50 mb-3">Active Learning</h2>
                            <p className="text-zinc-600 dark:text-zinc-400 max-w-md mx-auto leading-relaxed">
                                Dive into the core concepts of <span className="text-indigo-600 dark:text-indigo-400 font-bold underline underline-offset-4">{selectedDoc?.filename}</span> with interactive materials and AI-guided explanations.
                            </p>
                        </div>
                        <div className="pt-4 flex flex-col items-center gap-4">
                            <button
                                onClick={() => setIsActiveLearningStarted(true)}
                                className="w-full sm:w-auto px-12 py-4 rounded-2xl bg-indigo-600 text-white font-bold shadow-lg shadow-indigo-500/25 hover:bg-indigo-700 transition-all active:scale-95"
                            >
                                Start Learning
                            </button>
                            <button
                                onClick={() => {
                                    setCurrentFlow('pre-assessment');
                                }}
                                className="text-sm font-medium text-zinc-400 hover:text-zinc-600 transition-colors flex items-center space-x-1"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                                </svg>
                                <span>Change Material</span>
                            </button>
                        </div>
                        <button
                            onClick={() => setCurrentFlow('post-assessment')}
                            className="text-sm font-medium text-zinc-400 hover:text-zinc-600 transition-colors"
                        >
                            Mark as complete
                        </button>
                    </div>
                );
            case 'post-assessment':
                return (
                    <div className="space-y-6 text-center animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <div className="inline-flex h-20 w-20 items-center justify-center rounded-3xl bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400 mb-4">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-10 h-10">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <div>
                            <h2 className="text-3xl font-black text-zinc-900 dark:text-zinc-50 mb-3">Post-Assessment</h2>
                            <p className="text-zinc-600 dark:text-zinc-400 max-w-md mx-auto leading-relaxed">
                                Validate your knowledge of <span className="text-emerald-600 dark:text-emerald-400 font-bold underline underline-offset-4">{selectedDoc?.filename}</span> and identify areas that might need a quick review.
                            </p>
                        </div>
                        <div className="pt-4 flex flex-col items-center gap-4">
                            <button
                                onClick={handleStartPostAssessment}
                                className="w-full sm:w-auto px-12 py-4 rounded-2xl bg-emerald-600 text-white font-bold shadow-lg shadow-emerald-500/25 hover:bg-emerald-700 transition-all active:scale-95"
                            >
                                Start Final Check
                            </button>
                            <button
                                onClick={() => {
                                    setCurrentFlow('pre-assessment');
                                }}
                                className="text-sm font-medium text-zinc-400 hover:text-zinc-600 transition-colors flex items-center space-x-1"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                                </svg>
                                <span>Change Material</span>
                            </button>
                        </div>
                    </div>
                );

        }
    };

    return (
        <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 p-6 md:p-12 selection:bg-blue-100 selection:text-blue-700 dark:selection:bg-blue-900/30 dark:selection:text-blue-200">
            <header className="max-w-7xl mx-auto mb-16">
                <button
                    onClick={() => navigate(`/knowledge/${id}`)}
                    className="group mb-8 flex items-center space-x-2 text-sm font-bold text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="h-4 w-4 transition-transform group-hover:-translate-x-1">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                    </svg>
                    <span>Exit Study Session</span>
                </button>

                <div className="space-y-2">
                    <p className="text-blue-600 dark:text-blue-400 font-black uppercase tracking-widest text-xs">
                        {item?.name || itemFromList?.name || 'Knowledge'} • Topic {topicIndex !== -1 ? topicIndex + 1 : '...'}
                    </p>
                    <h1 className="text-4xl font-black tracking-tight text-zinc-900 dark:text-zinc-50">
                        {topic?.title || 'Study Session'}
                    </h1>
                </div>

                {/* Progress Bar */}


                <div className="mt-12 relative">
                    <div className="absolute top-1/2 left-0 w-full h-0.5 bg-zinc-200 dark:bg-zinc-800 -translate-y-1/2" />
                    <div 
                        className="absolute top-1/2 left-0 h-0.5 bg-blue-600 transition-all duration-700 ease-in-out -translate-y-1/2" 
                        style={{ width: `${(currentStepIndex / (steps.length - 1)) * 100}%` }}
                    />
                    
                    <div className="relative flex justify-between">
                        {steps.map((step, idx) => {
                            const isCompleted = idx < currentStepIndex;
                            const isActive = idx === currentStepIndex;
                            
                            
                            return (
                                <div key={step.id} className="flex flex-col items-center">
                                    <div 
                                        onClick={() => {
                                            setCurrentFlow(step.id as StudyFlow);
                                            setQuizStarted(false);
                                            setAssessmentResults(null);
                                            setIsGenerating(false);
                                            setIsSubmitting(false);
                                        }}
                                        className={`
                                            relative z-10 flex h-10 w-10 items-center justify-center rounded-full border-4 transition-all duration-500 cursor-pointer
                                            ${isActive ? 'bg-white border-blue-600 text-blue-600 dark:bg-zinc-900' : 
                                              'bg-zinc-100 border-zinc-200 text-zinc-400 dark:bg-zinc-800 dark:border-zinc-700'}
                                            ${isCompleted && !isActive ? 'bg-blue-600 border-blue-600 text-white' : ''}
                                        `}
                                    >
                                        {isCompleted && !isActive ? (
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor" className="w-5 h-5">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                                            </svg>
                                        ) : (
                                            <span className="text-sm font-bold">{idx + 1}</span>
                                        )}
                                    </div>
                                    <span className={`mt-3 text-xs font-black uppercase tracking-wider transition-colors duration-500 ${isActive ? 'text-blue-600' : 'text-zinc-400'}`}>
                                        {step.label}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto">
                <div className="bg-white dark:bg-zinc-900 rounded-[2.5rem] p-12 md:p-20 shadow-2xl shadow-zinc-200/50 dark:shadow-none ring-1 ring-zinc-200/50 dark:ring-zinc-800/50 border border-zinc-100 dark:border-zinc-800 min-h-[400px] flex items-center justify-center">
                    {isGenerating ? (
                        renderGeneratingUI()
                    ) : quizStarted ? (
                        renderQuizUI()
                    ) : assessmentResults ? (
                        renderResultsUI()
                    ) : (!selectedDocId && currentFlow !== 'pre-assessment') ? (
                        <div className="text-center space-y-6 animate-in fade-in zoom-in-95 duration-500">
                            <div className="inline-flex h-20 w-20 items-center justify-center rounded-3xl bg-zinc-50 text-zinc-400 dark:bg-zinc-800/50 mb-4 ring-1 ring-zinc-200 dark:ring-zinc-700">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-10 h-10">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                                </svg>
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">Select a file to begin</h2>
                                <p className="text-zinc-500 dark:text-zinc-400 max-w-xs mx-auto">
                                    Choose one of the materials in the Pre-Assessment stage to focus your study session.
                                </p>
                                <button 
                                    onClick={() => setCurrentFlow('pre-assessment')}
                                    className="mt-6 text-sm font-bold text-blue-600 hover:text-blue-700 transition-colors"
                                >
                                    Go to Pre-Assessment →
                                </button>
                            </div>
                        </div>
                    ) : (
                        renderFlowContent()
                    )}

                </div>
            </main>


        </div>
    );
}
