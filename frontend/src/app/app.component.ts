import {
    ChangeDetectorRef,
    Component,
    ViewChild,
    inject
} from '@angular/core';

import {
    CommonModule
} from '@angular/common';

import {
    FormsModule
} from '@angular/forms';

import {
    HttpErrorResponse
} from '@angular/common/http';

import {
    DomSanitizer,
    SafeResourceUrl
} from '@angular/platform-browser';

import {
    NgxChessBoardModule
} from './chessboard/ngx-chess-board.module';

import {
    NgxChessBoardView
} from './chessboard/ngx-chess-board-view';

import {
    MoveChange
} from './chessboard/engine/outputs/move-change/move-change';

import {
    AnalysisResponse,
    ErrorResponse,
    EvaluationType,
    Video
} from './analysis.model';

import {
    AnalysisService
} from './analysis.service';

import {
    AnalysisProgressEvent,
    ServiceType,
    WorkflowStep,
    WorkflowStepStatus
} from './analysis-progress.model';


// # Constantes

const STARTING_FEN =
    'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

const WHITE_TO_MOVE =
    'w';

const BLACK_TO_MOVE =
    'b';

const EVALUATION_TYPE_MATE: EvaluationType =
    'mate';

const CENTIPAWNS_PER_PAWN =
    100;


// # Camembert Lichess

const CHART_WHITE_COLOR =
    '#43ad7c';

const CHART_DRAW_COLOR =
    '#d5a52e';

const CHART_BLACK_COLOR =
    '#315ab4';


// # Vidéos

const SECONDS_PER_HOUR =
    3600;

const SECONDS_PER_MINUTE =
    60;

const YOUTUBE_EMBED_URL =
    'https://www.youtube.com/embed/';


// # Composant

@Component({
    selector: 'app-root',
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        NgxChessBoardModule
    ],
    templateUrl: './app.component.html',
    styleUrl: './app.component.scss'
})
export class AppComponent {

    @ViewChild('board')
    private board!: NgxChessBoardView;

    private readonly analysisService = inject(
        AnalysisService
    );

    private readonly changeDetector = inject(
        ChangeDetectorRef
    );

    private readonly sanitizer = inject(
        DomSanitizer
    );


    // # Position

    fen =
        STARTING_FEN;

    moves: string[] = [];


    // # Analyse

    analysis:
        AnalysisResponse | null = null;

    loading =
        false;


    // # Vidéo sélectionnée

    selectedVideo:
        Video | null = null;

    selectedVideoEmbedUrl:
        SafeResourceUrl | null = null;


    // # Progression

    currentStep:
        WorkflowStep | null = null;

    currentService:
        ServiceType | null = null;

    currentStepStatus:
        WorkflowStepStatus | null = null;

    completedSteps:
        WorkflowStep[] = [];

    stepStatuses: Partial<
        Record<
            WorkflowStep,
            WorkflowStepStatus
        >
    > = {};

    progressMessage:
        string | null = null;


    // # Erreurs

    fenError:
        string | null = null;

    analysisError:
        string | null = null;


    // # Échiquier

    onBoardMove(
        event: MoveChange
    ): void {
        this.fen =
            event.fen;

        this.clearPositionErrors();

        this.updateMoveHistory();
    }


    private updateMoveHistory(): void {
        const history =
            this.board.getMoveHistory();

        this.moves = history.map(
            historyMove =>
                historyMove.move
        );
    }


    // # FEN

    applyFen(): void {
        const fen =
            this.fen.trim();

        if (!fen) {
            this.fenError =
                'La position FEN est vide.';

            return;
        }

        try {
            this.board.setFEN(
                fen
            );

            this.fen =
                this.board.getFEN();

            /*
             * Une FEN saisie manuellement ne contient pas
             * l'historique des coups ayant conduit à la position.
             */
            this.moves =
                [];

            this.clearPositionErrors();

        } catch {
            this.fenError =
                'La position FEN est invalide.';
        }
    }


    private clearPositionErrors(): void {
        this.fenError =
            null;

        this.analysisError =
            null;
    }


    // # Analyse

    analyze(): void {
        if (this.loading) {
            return;
        }

        const fen =
            this.fen.trim();

        if (!fen) {
            this.fenError =
                'La position FEN est vide.';

            return;
        }

        this.prepareAnalysis();

        this.analysisService
            .analyzeStream(
                fen,
                this.moves
            )
            .subscribe({
                next: event => {
                    switch (event.event) {

                        case 'progress':
                            this.handleProgressEvent(
                                event
                            );
                            break;

                        case 'completed':
                            this.handleAnalysisSuccess(
                                event.analysis
                            );
                            break;
                    }
                },

                error: (
                    error: unknown
                ) => {
                    this.handleAnalysisError(
                        error
                    );
                }
            });
    }


    private prepareAnalysis(): void {
        this.loading =
            true;

        this.analysis =
            null;

        this.analysisError =
            null;

        this.closeVideo();

        this.resetProgress();

        this.changeDetector.detectChanges();
    }


    private handleProgressEvent(
        event: AnalysisProgressEvent
    ): void {
        this.currentStep =
            event.step;

        this.currentService =
            event.service;

        this.currentStepStatus =
            event.status;

        this.completedSteps = [
            ...event.completed_steps
        ];

        this.progressMessage =
            event.message;

        this.stepStatuses = {
            ...this.stepStatuses,
            [event.step]:
                event.status
        };

        for (
            const completedStep
            of event.completed_steps
        ) {
            this.stepStatuses[
                completedStep
            ] = 'completed';
        }

        this.changeDetector.detectChanges();
    }


    private handleAnalysisSuccess(
        response: AnalysisResponse
    ): void {
        this.analysis =
            response;

        this.loading =
            false;

        this.currentStep =
            null;

        this.currentService =
            null;

        this.currentStepStatus =
            null;

        this.progressMessage =
            null;

        this.analysisError =
            response.error ?? null;

        this.changeDetector.detectChanges();
    }


    private handleAnalysisError(
        error: unknown
    ): void {
        this.analysis =
            null;

        this.loading =
            false;

        this.closeVideo();

        if (
            this.currentStep !== null
        ) {
            this.stepStatuses = {
                ...this.stepStatuses,
                [this.currentStep]:
                    'failed'
            };
        }

        this.currentStepStatus =
            'failed';

        this.analysisError =
            this.extractErrorMessage(
                error
            );

        this.progressMessage =
            this.analysisError;

        this.changeDetector.detectChanges();
    }


    private extractErrorMessage(
        error: unknown
    ): string {
        if (
            error instanceof HttpErrorResponse
        ) {
            const payload =
                error.error as ErrorResponse | null;

            return (
                payload
                    ?.error
                    ?.message
                ?? 'Impossible de récupérer l’analyse.'
            );
        }

        if (
            error instanceof Error
        ) {
            return error.message;
        }

        return (
            'Impossible de récupérer l’analyse.'
        );
    }


    // # Progression

    private resetProgress(): void {
        this.currentStep =
            null;

        this.currentService =
            null;

        this.currentStepStatus =
            null;

        this.completedSteps =
            [];

        this.stepStatuses =
            {};

        this.progressMessage =
            null;
    }


    isStepCompleted(
        step: WorkflowStep
    ): boolean {
        return (
            this.stepStatuses[
                step
            ] === 'completed'
        );
    }


    isStepRunning(
        step: WorkflowStep
    ): boolean {
        return (
            this.stepStatuses[
                step
            ] === 'running'
        );
    }


    isStepWarning(
        step: WorkflowStep
    ): boolean {
        return (
            this.stepStatuses[
                step
            ] === 'warning'
        );
    }


    isStepFailed(
        step: WorkflowStep
    ): boolean {
        return (
            this.stepStatuses[
                step
            ] === 'failed'
        );
    }


    // # Réinitialisation

    reset(): void {
        if (this.loading) {
            return;
        }

        this.analysis =
            null;

        this.analysisError =
            null;

        this.fenError =
            null;

        this.moves =
            [];

        this.closeVideo();

        this.resetProgress();

        this.board.reset();

        this.fen =
            this.board.getFEN();

        this.changeDetector.detectChanges();
    }


    // # Position

    get sideToMoveLabel(): string {
        const sideToMove =
            this.getFenSideToMove();

        if (
            sideToMove
            === WHITE_TO_MOVE
        ) {
            return 'Blancs';
        }

        if (
            sideToMove
            === BLACK_TO_MOVE
        ) {
            return 'Noirs';
        }

        return '—';
    }


    private getFenSideToMove():
        string | null {

        const fields =
            this.fen
                .trim()
                .split(
                    /\s+/
                );

        return fields[1] ?? null;
    }


    // # Document

    get wikichessDocument():
        AnalysisResponse[
            'documents'
        ][number] | null {

        return this.analysis
            ?.documents
            .find(
                document =>
                    document
                        .metadata
                        .source
                        .toLowerCase()
                        .includes(
                            'wikichess'
                        )
                    && document
                        .metadata
                        .url !== null
            )
            ?? null;
    }


    // # Statistiques Lichess

    get lichessChartStyle(): string {
        const statistics =
            this.analysis
                ?.opening
                ?.statistics;

        if (!statistics) {
            return '';
        }

        const whiteRate =
            statistics.white_win_rate;

        const drawRate =
            statistics.draw_rate;

        const blackRate =
            statistics.black_win_rate;

        const total =
            whiteRate
            + drawRate
            + blackRate;

        if (total <= 0) {
            return '';
        }

        const whiteEnd =
            (
                whiteRate
                / total
            ) * 100;

        const drawEnd =
            whiteEnd
            + (
                drawRate
                / total
            ) * 100;

        return (
            `conic-gradient(`
            + `${CHART_WHITE_COLOR} `
            + `0% ${whiteEnd}%, `
            + `${CHART_DRAW_COLOR} `
            + `${whiteEnd}% ${drawEnd}%, `
            + `${CHART_BLACK_COLOR} `
            + `${drawEnd}% 100%`
            + `)`
        );
    }


    // # Vidéos

    openVideo(
        video: Video
    ): void {
        this.selectedVideo =
            video;

        const embedUrl =
            `${YOUTUBE_EMBED_URL}`
            + `${encodeURIComponent(video.id)}`
            + '?autoplay=1&rel=0';

        this.selectedVideoEmbedUrl =
            this.sanitizer
                .bypassSecurityTrustResourceUrl(
                    embedUrl
                );

        this.changeDetector.detectChanges();
    }


    closeVideo(): void {
        this.selectedVideo =
            null;

        this.selectedVideoEmbedUrl =
            null;
    }


    formatVideoDuration(
        seconds: number
    ): string {
        const hours =
            Math.floor(
                seconds
                / SECONDS_PER_HOUR
            );

        const minutes =
            Math.floor(
                (
                    seconds
                    % SECONDS_PER_HOUR
                )
                / SECONDS_PER_MINUTE
            );

        const remainingSeconds =
            seconds
            % SECONDS_PER_MINUTE;

        if (hours > 0) {
            return (
                `${hours}:`
                + `${minutes
                    .toString()
                    .padStart(
                        2,
                        '0'
                    )}:`
                + `${remainingSeconds
                    .toString()
                    .padStart(
                        2,
                        '0'
                    )}`
            );
        }

        return (
            `${minutes}:`
            + `${remainingSeconds
                .toString()
                .padStart(
                    2,
                    '0'
                )}`
        );
    }


    formatCompactNumber(
        value: number
    ): string {
        return new Intl.NumberFormat(
            'fr-FR',
            {
                notation:
                    'compact',
                maximumFractionDigits:
                    1
            }
        ).format(
            value
        );
    }


    // # Affichage

    get evaluationLabel(): string {
        const evaluation =
            this.analysis
                ?.evaluation
                ?.engine
                .evaluation;

        if (!evaluation) {
            return '—';
        }

        return this.formatScore(
            evaluation.score,
            evaluation.evaluation_type
        );
    }


    formatScore(
        score: number,
        evaluationType: EvaluationType
    ): string {
        if (
            evaluationType
            === EVALUATION_TYPE_MATE
        ) {
            return `Mat ${score}`;
        }

        const pawnScore =
            score
            / CENTIPAWNS_PER_PAWN;

        const sign =
            pawnScore > 0
                ? '+'
                : '';

        return (
            `${sign}${pawnScore.toFixed(2)}`
        );
    }
}