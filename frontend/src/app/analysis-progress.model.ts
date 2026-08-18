import { AnalysisResponse } from './analysis.model';


export type WorkflowStep =
  | 'validate_position'
  | 'detect_theory'
  | 'engine_analysis'
  | 'unknown_position_analysis'
  | 'retrieve_context'
  | 'retrieve_videos'
  | 'generate_response'
  | 'save_analysis';


export type WorkflowStepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'warning'
  | 'failed';


export type ServiceType =
  | 'chess'
  | 'stockfish'
  | 'lichess'
  | 'embedding'
  | 'milvus'
  | 'vector_search'
  | 'youtube'
  | 'llm'
  | 'mongodb'
  | 'langgraph';


export interface AnalysisProgressEvent {
  event: 'progress';
  request_id: string;
  step: WorkflowStep;
  service: ServiceType | null;
  status: WorkflowStepStatus;
  completed_steps: WorkflowStep[];
  message: string | null;
}


export interface AnalysisCompletedEvent {
  event: 'completed';
  request_id: string;
  analysis: AnalysisResponse;
}


export type AnalysisStreamEvent =
  | AnalysisProgressEvent
  | AnalysisCompletedEvent;