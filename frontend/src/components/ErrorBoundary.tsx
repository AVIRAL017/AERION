import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Diagnostic logging for development while protecting operational privacy
    console.error('[AERION ErrorBoundary] Uncaught UI render exception:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/border';
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen w-screen flex items-center justify-center bg-graphite telemetry-grid p-6 text-paper font-mono">
          <div className="max-w-md w-full p-6 rounded-lg bg-panel border border-status-critical/40 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded bg-status-critical/10 border border-status-critical/30 flex items-center justify-center text-status-critical">
                <span className="material-symbols-outlined text-[20px]">warning</span>
              </div>
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider text-paper">
                  OPERATIONAL INTERFACE EXCEPTION
                </h2>
                <span className="text-[10px] text-faint">CLIENT RUNTIME FAULT DETECTED</span>
              </div>
            </div>

            <p className="text-xs text-muted leading-relaxed">
              A rendering anomaly occurred while processing incoming telemetry. Safe boundary isolation engaged to preserve session state and prevent system desynchronization.
            </p>

            <div className="p-3 bg-graphite/80 rounded border border-white/[0.06] text-[11px] text-faint break-all">
              {this.state.error?.message || 'Unexpected component evaluation failure'}
            </div>

            <div className="pt-2 flex justify-end gap-3">
              <button
                onClick={this.handleReset}
                className="px-4 py-2 rounded bg-accent/15 border border-accent/40 text-accent text-xs font-bold uppercase tracking-wider hover:bg-accent/25 transition-all flex items-center gap-1.5"
              >
                <span className="material-symbols-outlined text-[15px]">refresh</span>
                <span>Return to Operational Console</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
