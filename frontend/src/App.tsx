import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { BorderPage } from './pages/BorderPage';
import { DisasterPage } from './pages/DisasterPage';
import { EvacuationPage } from './pages/EvacuationPage';
import { SituationReportPage } from './pages/SituationReportPage';
import { UsagePage } from './pages/UsagePage';
import { SystemStatusPage } from './pages/SystemStatusPage';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          {/* Core Authenticated App Layout */}
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/border" replace />} />
            <Route path="/border" element={<BorderPage />} />
            <Route path="/disaster" element={<DisasterPage />} />
            <Route path="/disaster/damage" element={<DisasterPage />} />
            <Route path="/disaster/evacuation" element={<EvacuationPage />} />
            <Route path="/situations/:id/report" element={<SituationReportPage />} />
            <Route path="/usage" element={<UsagePage />} />
            <Route path="/status" element={<SystemStatusPage />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/border" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
