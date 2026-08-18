import {
    inject,
    Injectable
} from '@angular/core';

import {
    HttpClient
} from '@angular/common/http';

import {
    Observable
} from 'rxjs';

import {
    AnalysisRequest,
    AnalysisResponse
} from './analysis.model';

import {
    AnalysisStreamEvent
} from './analysis-progress.model';


// # Configuration

const ANALYSIS_URL =
    '/api/v1/analysis/position';

const ANALYSIS_STREAM_URL =
    '/api/v1/analysis/stream';


// # Service

@Injectable({
    providedIn: 'root'
})
export class AnalysisService {

    private readonly http = inject(
        HttpClient
    );


    // # Analyse

    analyze(
        fen: string,
        moves: string[]
    ): Observable<AnalysisResponse> {
        const payload: AnalysisRequest = {
            fen,
            moves
        };

        return this.http.post<AnalysisResponse>(
            ANALYSIS_URL,
            payload
        );
    }


    analyzeStream(
        fen: string,
        moves: string[]
    ): Observable<AnalysisStreamEvent> {
        const payload: AnalysisRequest = {
            fen,
            moves
        };

        return new Observable<AnalysisStreamEvent>(
            subscriber => {
                const controller =
                    new AbortController();

                void this.readStream(
                    payload,
                    subscriber,
                    controller.signal
                );

                return () => {
                    controller.abort();
                };
            }
        );
    }


    // # Streaming

    private async readStream(
        payload: AnalysisRequest,
        subscriber: {
            next: (
                event: AnalysisStreamEvent
            ) => void;
            error: (
                error: unknown
            ) => void;
            complete: () => void;
        },
        signal: AbortSignal
    ): Promise<void> {
        try {
            const response = await fetch(
                ANALYSIS_STREAM_URL,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type':
                            'application/json',
                        Accept:
                            'text/event-stream'
                    },
                    body: JSON.stringify(
                        payload
                    ),
                    signal
                }
            );

            if (!response.ok) {
                throw new Error(
                    `Erreur HTTP ${response.status}`
                );
            }

            if (response.body === null) {
                throw new Error(
                    'Le serveur n’a retourné aucun flux.'
                );
            }

            const reader = response.body
                .pipeThrough(
                    new TextDecoderStream()
                )
                .getReader();

            let buffer = '';

            while (true) {
                const result =
                    await reader.read();

                if (result.done) {
                    break;
                }

                buffer += result.value;

                const chunks = buffer.split(
                    /\r?\n\r?\n/
                );
                
                buffer =
                    chunks.pop() ?? '';

                for (const chunk of chunks) {
                    const event =
                        this.parseSseEvent(
                            chunk
                        );

                    if (event !== null) {
                        subscriber.next(
                            event
                        );
                    }
                }
            }

            subscriber.complete();

        } catch (error) {
            if (
                error instanceof DOMException
                && error.name === 'AbortError'
            ) {
                return;
            }

            subscriber.error(
                error
            );
        }
    }


    private parseSseEvent(
        chunk: string
    ): AnalysisStreamEvent | null {
        const lines = chunk.split(
            /\r?\n/
        );

        let eventType:
            string | null = null;

        const dataLines: string[] = [];

        for (const line of lines) {

            if (
                line.startsWith(
                    'event:'
                )
            ) {
                eventType = line
                    .slice(
                        'event:'.length
                    )
                    .trim();

                continue;
            }

            if (
                line.startsWith(
                    'data:'
                )
            ) {
                dataLines.push(
                    line
                        .slice(
                            'data:'.length
                        )
                        .trimStart()
                );
            }
        }

        if (
            eventType === null
            || dataLines.length === 0
        ) {
            return null;
        }

        if (
            eventType !== 'progress'
            && eventType !== 'completed'
        ) {
            return null;
        }

        const data = dataLines.join(
            '\n'
        );

        return JSON.parse(
            data
        ) as AnalysisStreamEvent;
    }
}