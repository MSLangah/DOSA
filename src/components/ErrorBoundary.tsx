import React from 'react';
export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) return <div className="min-h-screen grid place-items-center">Something went wrong. Please refresh.</div>;
    return this.props.children;
  }
}
