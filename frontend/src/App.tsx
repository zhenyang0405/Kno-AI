import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { onAuthStateChanged, signInAnonymously, type User } from 'firebase/auth';
import { auth } from './firebase';
import { saveKnowledge, getKnowledgeList } from './services/api';
import LandingPage from './pages/LandingPage';
import KnowledgeDashboard from './pages/KnowledgeDashboard';
import DocumentViewer from '../others/DocumentViewer';
import StudySession from './pages/StudySession';
import OnboardingPage from './pages/OnboardingPage';
import type { KnowledgeItem } from './types';

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [knowledgeList, setKnowledgeList] = useState<KnowledgeItem[]>([]);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      if (currentUser) {
        setUser(currentUser);
        setLoading(false);
      } else {
        signInAnonymously(auth)
          .then(() => {
            // signInAnonymously will trigger onAuthStateChanged again
          })
          .catch((error) => {
            console.error("Error signing in anonymously:", error);
            setLoading(false);
          });
      }
    });

    return () => unsubscribe();
  }, []);

  // Fetch knowledge list when user is authenticated
  const fetchKnowledgeList = async () => {
    if (!user) return;
    
    try {
      const data = await getKnowledgeList();
      setKnowledgeList(data);
    } catch (error) {
      console.error("Error fetching knowledge list:", error);
    }
  };

  // Fetch knowledge list from API on mount
  useEffect(() => {
    if (!user) return;
    fetchKnowledgeList();
  }, [user]);

  const handleAddKnowledge = async (name: string, description: string) => {
    if (!user) return;

    try {
      await saveKnowledge(name, description);
      // Refresh knowledge list after adding
      await fetchKnowledgeList();
    } catch (error) {
      console.error("Error adding knowledge through backend:", error);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-blue-600 border-t-transparent shadow-lg text-blue-600"></div>
      </div>
    );
  }

  return (
    <Router>
      <div className="relative">
        {/* User Info Badge */}
        {user && (
          <div className="fixed bottom-4 right-4 z-50 rounded-full bg-white/80 px-4 py-2 text-[10px] font-medium text-zinc-500 shadow-sm backdrop-blur-md dark:bg-zinc-900/80 dark:text-zinc-400 ring-1 ring-zinc-200 dark:ring-zinc-800">
            <span className="flex items-center space-x-2">
              <span className="h-2 w-2 rounded-full bg-green-500"></span>
              <span>ID: {user.uid.slice(0, 8)}...</span>
            </span>
          </div>
        )}

        <Routes>
          <Route
            path="/"
            element={
              <LandingPage
                user={user}
                knowledgeList={knowledgeList}
                onAddKnowledge={handleAddKnowledge}
              />
            }
          />
          <Route
            path="/onboarding"
            element={<OnboardingPage />}
          />
          <Route
            path="/knowledge/:id"
            element={<KnowledgeDashboard knowledgeList={knowledgeList} />}
          />
          <Route
            path="/knowledge/:id/document/:docId"
            element={<DocumentViewer />}
          />
          <Route
            path="/knowledge/:id/topic/:topicId/study"
            element={<StudySession knowledgeList={knowledgeList} />}
          />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
