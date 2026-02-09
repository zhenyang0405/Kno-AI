export interface Topic {
    id: string;
    title: string;
    description?: string;
}

export interface KnowledgeItem {
    id: string;
    name: string;
    description: string;
    overview?: string;
    topics?: Topic[];
    grade?: string;
}

export interface DocumentItem {
    id: string;
    filename: string;
    url: string;
    storagePath: string;
    storageBucket?: string;
    uploadedAt: { seconds: number; nanoseconds: number } | Date;
    topicId?: string;
}

export interface Annotation {
    id: string;
    type: 'highlight' | 'note' | 'drawing';
    pageNumber: number;
    color?: string;
    comment?: string;
    position: {
        boundingRect: {
            x: number;
            y: number;
            width: number;
            height: number;
        };
        rects: Array<{
            x: number;
            y: number;
            width: number;
            height: number;
        }>;
        path?: Array<{ x: number; y: number }>;
    };
    text?: string;
    createdAt: Date | { seconds: number; nanoseconds: number };
}
