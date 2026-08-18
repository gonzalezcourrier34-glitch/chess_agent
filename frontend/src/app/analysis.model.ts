// Modèles utilisés par la page d'analyse.


// # Types

export type AnalysisStatus =
    | 'pending'
    | 'success'
    | 'partial_success'
    | 'failed';


export type EvaluationType =
    | 'centipawn'
    | 'mate';


// # Requête

export interface AnalysisRequest {
    fen: string;
    moves: string[];
    question?: string;
    response_language?: string;
}


// # Réponse

export interface AnalysisResponse {
    status: AnalysisStatus;
    fen: string;

    opening: OpeningDetails | null;
    evaluation: PositionEvaluation | null;

    documents: Document[];
    videos: Video[];

    explanation: string | null;
    analysis_id: string | null;
    error: string | null;
}


// # Ouverture

export interface OpeningDetails {
    opening: Opening;
    statistics: OpeningStatistics | null;
}


export interface Opening {
    eco: string;
    name: string;
    variation: string | null;
}


export interface OpeningStatistics {
    games: number;
    white_win_rate: number;
    black_win_rate: number;
    draw_rate: number;
    average_rating: number | null;
}


// # Stockfish

export interface PositionEvaluation {
    engine: EngineAnalysis;
}


export interface EngineAnalysis {
    best_move: BestMove | null;
    evaluation: Evaluation;
    principal_variation: PrincipalVariation;
    alternatives: BestMove[];
}


export interface Evaluation {
    score: number;
    evaluation_type: EvaluationType;
    depth: number;
    nodes: number | null;
    time_ms: number | null;
}


export interface PrincipalVariation {
    moves: string[];
    evaluation: Evaluation;
    explanation: string | null;
}


export interface BestMove {
    uci: string;
    san: string;
    score: number;
    evaluation_type: EvaluationType;
    depth: number;
    principal_variation: string[];
}


// # Documents

export interface Document {
    id: string;
    type: string;
    title: string;
    content: string;
    metadata: DocumentMetadata;
}


export interface DocumentMetadata {
    source: string;
    language: string;

    author: string | null;
    url: string | null;
    publication_date: string | null;

    eco: string | null;

    moves: string[];
    moves_path: string | null;

    position_after: string | null;

    wikichess_title: string | null;

    next_moves: DocumentNextMove[];
}


export interface DocumentNextMove {
    move: string;
    source_url: string;
}


// # Vidéos

export interface Video {
    id: string;

    platform: string;

    title: string;
    description: string | null;

    url: string;
    thumbnail_url: string | null;

    duration_seconds: number | null;

    view_count: number | null;
    like_count: number | null;
    comment_count: number | null;

    published_at: string | null;

    channel: VideoChannel;

    language: string | null;
}


export interface VideoChannel {
    id: string | null;
    name: string;
    url: string | null;
    subscribers: number | null;
}


// # Erreurs

export interface ApiError {
    code: string;
    message: string;
    status_code: number;
}


export interface ErrorResponse {
    error: ApiError;
    request_id: string | null;
}