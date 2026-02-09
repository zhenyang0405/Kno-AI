import { auth } from '../firebase';

// const BASE_URL = 'http://localhost:8000';
const BASE_URL = 'https://backend-service-460848097230.us-east1.run.app';

const getAuthHeaders = async () => {
    const user = auth.currentUser;
    if (!user) throw new Error('User not authenticated');

    const token = await user.getIdToken();
    return {
        'Authorization': `Bearer ${token}`,
    };
};

export const saveKnowledge = async (name: string, description: string) => {
    const headers = await getAuthHeaders();
    const formData = new FormData();
    formData.append('name', name);
    formData.append('description', description);

    const response = await fetch(`${BASE_URL}/save-knowledge`, {
        method: 'POST',
        headers,
        body: formData,
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save knowledge');
    }

    return response.json();
};

export const uploadDocument = async (knowledgeId: string, file: File, topicId?: string) => {
    const headers = await getAuthHeaders();
    const formData = new FormData();
    formData.append('knowledge_id', knowledgeId);
    if (topicId) formData.append('topic_id', topicId);
    formData.append('file', file);

    const response = await fetch(`${BASE_URL}/upload-document`, {
        method: 'POST',
        headers,
        body: formData,
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to upload document');
    }

    return response.json();
};

export const deleteDocument = async (knowledgeId: string, documentId: string) => {
    const headers = await getAuthHeaders();

    const response = await fetch(`${BASE_URL}/delete-document/${knowledgeId}/${documentId}`, {
        method: 'DELETE',
        headers,
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete document');
    }

    return response.json();
};

// GET endpoints
export const getKnowledgeList = async () => {
    const headers = await getAuthHeaders();

    const response = await fetch(`${BASE_URL}/knowledge`, {
        method: 'GET',
        headers,
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch knowledge list');
    }

    const data = await response.json();
    return data.knowledge;
};

export const getKnowledgeDetails = async (knowledgeId: string) => {
    const headers = await getAuthHeaders();

    const response = await fetch(`${BASE_URL}/knowledge/${knowledgeId}`, {
        method: 'GET',
        headers,
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch knowledge details');
    }

    const data = await response.json();
    return data.knowledge;
};

export const getKnowledgeDocuments = async (knowledgeId: string) => {
    const headers = await getAuthHeaders();

    const response = await fetch(`${BASE_URL}/knowledge/${knowledgeId}/documents`, {
        method: 'GET',
        headers,
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch knowledge documents');
    }

    const data = await response.json();
    return data.documents;
};

export const getDocumentDetails = async (documentId: string) => {
    const headers = await getAuthHeaders();

    const response = await fetch(`${BASE_URL}/documents/${documentId}`, {
        method: 'GET',
        headers,
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch document details');
    }

    const data = await response.json();
    return data.document;
};

export const getDocumentDownloadUrl = async (documentId: string) => {
    const headers = await getAuthHeaders();

    const response = await fetch(`${BASE_URL}/documents/${documentId}/download-url`, {
        method: 'GET',
        headers,
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch download URL');
    }

    const data = await response.json();
    return data.url;
};
