import { auth } from '../firebase';

// Active Learning Service - Interactive AI chat (port 8002)
const ACTIVE_LEARNING_URL = 'http://localhost:8002';

// Pre-Active-Learn Service - Workspace prep, sessions, caching (port 8001)  
const PRE_ACTIVE_LEARN_URL = 'https://pre-active-learn-agent-460848097230.us-east1.run.app';
// const PRE_ACTIVE_LEARN_URL = 'http://localhost:8003';

const BASE_URL = ACTIVE_LEARNING_URL; // For backward compatibility with ask endpoint

export interface InitializeSessionRequest {
    session_id: number;
    user_id: number;
}

const getAuthHeaders = async () => {
    const user = auth.currentUser;
    if (!user) throw new Error('User not authenticated');

    const token = await user.getIdToken();
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
    };
};

export interface AskRequest {
    user_question: string;
    workspace_session_id: number;
    user_id: number;
    current_page?: number;
}

export interface ContentResponse {
    response_type: string;
    chat_response: string;
    content?: {
        type: 'text' | 'math' | 'animation' | 'image' | 'adaptive_guide';
        data: any;
        format?: string;
        metadata?: any;
        concept_id?: string;
        concept_name?: string;
    };
    delegation_payload?: any;
    concept_updates?: Array<{
        concept_id: string;
        new_status: string;
        source: string;
    }>;
    followup_suggestions?: string[];
}

export const askOrchestrator = async (request: AskRequest): Promise<ContentResponse> => {
    const headers = await getAuthHeaders();
    
    console.log('Asking orchestrator with request:', request);
    console.log('Headers:', headers);

    const response = await fetch(`${BASE_URL}/api/active-learning/ask`, {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to ask orchestrator');
    }

    return response.json();
};

export interface InitializeWorkspaceRequest {
    study_session_id: number;
    user_id: number;
}

export interface InitializeWorkspaceResponse {
    success: boolean;
    study_session_id: number;
    material_id: number;
    cache_status: 'exists' | 'creating';
    message: string;
}

export const initializeWorkspace = async (request: InitializeWorkspaceRequest): Promise<InitializeWorkspaceResponse> => {
    const headers = await getAuthHeaders();
    
    console.log('Initializing workspace with request:', request);

    const response = await fetch(`${PRE_ACTIVE_LEARN_URL}/api/pre-active-learn/initialize-workspace`, {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to initialize workspace');
    }

    return response.json();
};

export interface CreateStudySessionRequest {
    user_id: number;
    material_id: number;
    pre_assessment_id?: number;
    weak_concepts?: string[];
}

export interface StudySessionResponse {
    success: boolean;
    session: {
        id: number;
        user_id: number;
        material_id: number;
        pre_assessment_id?: number;
        weak_concepts?: any;
        status: string;
        started_at: string;
        created_at: string;
    };
    message: string;
}

export const createStudySession = async (request: CreateStudySessionRequest): Promise<StudySessionResponse> => {
    const headers = await getAuthHeaders();
    
    console.log('Creating study session with request:', request);

    const response = await fetch(`${PRE_ACTIVE_LEARN_URL}/api/pre-active-learn/study-sessions`, {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create study session');
    }

    return response.json();
};

export interface GetUserResponse {
    success: boolean;
    user: {
        id: number;
        firebase_uid: string;
        email?: string;
        name?: string;
        created_at: string;
        updated_at: string;
    };
}

export const getUserId = async (firebaseUid: string): Promise<number> => {
    const headers = await getAuthHeaders();
    
    console.log('Getting user ID for Firebase UID:', firebaseUid);

    const response = await fetch(`${PRE_ACTIVE_LEARN_URL}/api/pre-active-learn/users/get-or-create`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
            firebase_uid: firebaseUid,
        }),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to get user ID');
    }

    const data: GetUserResponse = await response.json();
    return data.user.id;
};

export const initializeSession = async (request: InitializeSessionRequest): Promise<ContentResponse> => {
    const headers = await getAuthHeaders();
    
    console.log('Initializing session with request:', request);

    const response = await fetch(`${BASE_URL}/api/active-learning/initialize-session`, {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to initialize session');
    }

    return response.json();
};
