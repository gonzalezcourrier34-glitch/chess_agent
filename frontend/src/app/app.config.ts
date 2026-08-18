import {
    ApplicationConfig,
    importProvidersFrom
} from '@angular/core';
import { provideHttpClient } from '@angular/common/http';

import {
    NgxChessBoardModule
} from './chessboard/ngx-chess-board.module';


// Configuration

export const appConfig: ApplicationConfig = {
    providers: [
        provideHttpClient(),
        importProvidersFrom(
            NgxChessBoardModule.forRoot()
        )
    ]
};