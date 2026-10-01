import React, { useEffect, useState, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { authApi, usageApi } from '../api';
import { UsageSummary } from '../types';

type SettingsTab = 'profile' | 'security' | 'account' | 'notifications' | 'interface';

export const AccountPage: React.FC = () => {
  const { user, logout, updateUser } = useAuth();
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [isLoadingUsage, setIsLoadingUsage] = useState<boolean>(true);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState<boolean>(false);
  const [showRemoveAvatarConfirm, setShowRemoveAvatarConfirm] = useState<boolean>(false);

  // Profile Form State
  const [displayName, setDisplayName] = useState<string>('');
  const [profileSaveStatus, setProfileSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [profileMessage, setProfileMessage] = useState<string>('');

  // Avatar State
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [avatarUploadStatus, setAvatarUploadStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [avatarMessage, setAvatarMessage] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Security Form State
  const [currentPassword, setCurrentPassword] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [passwordStatus, setPasswordStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [passwordMessage, setPasswordMessage] = useState<string>('');

  // Notification Preferences State
  const [notifLoginAlerts, setNotifLoginAlerts] = useState<boolean>(true);
  const [notifAnalysisComplete, setNotifAnalysisComplete] = useState<boolean>(true);
  const [notifThreatAlerts, setNotifThreatAlerts] = useState<boolean>(true);
  const [notifReportReady, setNotifReportReady] = useState<boolean>(true);
  const [notifStatus, setNotifStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [notifMessage, setNotifMessage] = useState<string>('');

  // Interface Preferences State
  const [reducedMotion, setReducedMotion] = useState<boolean>(false);
  const [interfaceDensity, setInterfaceDensity] = useState<'comfortable' | 'compact'>('comfortable');
  const [spatialEffects, setSpatialEffects] = useState<boolean>(true);
  const [defaultPage, setDefaultPage] = useState<string>('/border');
  const [interfaceStatus, setInterfaceStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [interfaceMessage, setInterfaceMessage] = useState<string>('');

  // Initialize from user profile and preferences
  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name || '');
      setAvatarPreview(user.avatar_url || null);
      if (user.preferences) {
        const notifs = user.preferences.notifications || {};
        if (typeof notifs.login_alerts === 'boolean') setNotifLoginAlerts(notifs.login_alerts);
        if (typeof notifs.analysis_complete === 'boolean') setNotifAnalysisComplete(notifs.analysis_complete);
        if (typeof notifs.threat_alerts === 'boolean') setNotifThreatAlerts(notifs.threat_alerts);
        if (typeof notifs.report_ready === 'boolean') setNotifReportReady(notifs.report_ready);

        const ui = user.preferences.interface || {};
        if (typeof ui.reduced_motion === 'boolean') setReducedMotion(ui.reduced_motion);
        if (ui.density) setInterfaceDensity(ui.density);
        if (typeof ui.spatial_effects === 'boolean') setSpatialEffects(ui.spatial_effects);
        if (ui.default_page) setDefaultPage(ui.default_page);
      }
    }
  }, [user]);

  useEffect(() => {
    const fetchUsage = async () => {
      try {
        const res = await usageApi.getSummary();
        if (res.success && res.data) {
          setUsage(res.data);
        }
      } catch {
        // Fallback
      } finally {
        setIsLoadingUsage(false);
      }
    };
    fetchUsage();
  }, []);

  if (!user) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-50 font-mono text-xs text-slate-500">
        NO ACTIVE OPERATOR SESSION DETECTED.
      </div>
    );
  }

  const isGoogle = user.auth_provider === 'google';

  // Password Strength Calculation
  const calculatePasswordStrength = (pwd: string) => {
    let score = 0;
    if (pwd.length >= 8) score += 1;
    if (pwd.length >= 12) score += 1;
    if (/[A-Z]/.test(pwd)) score += 1;
    if (/[0-9]/.test(pwd)) score += 1;
    if (/[^A-Za-z0-9]/.test(pwd)) score += 1;
    return score;
  };
  const passwordStrengthScore = calculatePasswordStrength(newPassword);

  // Handle Profile Update (Display Name)
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSaveStatus('saving');
    setProfileMessage('');
    try {
      const res = await authApi.updateProfile({ display_name: displayName.trim() });
      if (res.success && res.data) {
        updateUser(res.data);
        setProfileSaveStatus('success');
        setProfileMessage('Operator profile successfully updated.');
        setTimeout(() => setProfileSaveStatus('idle'), 3500);
      } else {
        setProfileSaveStatus('error');
        setProfileMessage(res.error || 'Failed to update profile.');
      }
    } catch (err: any) {
      setProfileSaveStatus('error');
      setProfileMessage(err?.response?.data?.detail || 'Network error updating profile.');
    }
  };

  // Handle Avatar File Selection & Upload
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side Validation: type & size (<= 2MB)
    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      setAvatarUploadStatus('error');
      setAvatarMessage('Unsupported format. Please select JPEG, PNG, or WebP.');
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      setAvatarUploadStatus('error');
      setAvatarMessage('File exceeds 2MB limit. Please select a smaller image.');
      return;
    }

    // Read as Base64 for Preview & Upload
    const reader = new FileReader();
    reader.onload = async () => {
      const base64Data = reader.result as string;
      setAvatarPreview(base64Data);
      setAvatarUploadStatus('saving');
      setAvatarMessage('Uploading and processing avatar thumbnail...');

      try {
        const res = await authApi.uploadAvatar(base64Data);
        if (res.success && res.data) {
          updateUser(res.data);
          setAvatarUploadStatus('success');
          setAvatarMessage('Avatar successfully updated and persisted.');
          setTimeout(() => setAvatarUploadStatus('idle'), 3500);
        } else {
          setAvatarUploadStatus('error');
          setAvatarMessage(res.error || 'Server rejected avatar.');
          setAvatarPreview(user.avatar_url || null);
        }
      } catch (err: any) {
        setAvatarUploadStatus('error');
        setAvatarMessage(err?.response?.data?.detail || 'Failed to upload avatar.');
        setAvatarPreview(user.avatar_url || null);
      }
    };
    reader.readAsDataURL(file);
    // Reset file input value so re-selecting same file triggers change
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Handle Avatar Removal
  const handleConfirmRemoveAvatar = async () => {
    setShowRemoveAvatarConfirm(false);
    setAvatarUploadStatus('saving');
    setAvatarMessage('Removing operator avatar...');

    try {
      const res = await authApi.deleteAvatar();
      if (res.success && res.data) {
        updateUser(res.data);
        setAvatarPreview(null);
        setAvatarUploadStatus('success');
        setAvatarMessage('Avatar removed. Reverted to standard initials.');
        setTimeout(() => setAvatarUploadStatus('idle'), 3500);
      } else {
        setAvatarUploadStatus('error');
        setAvatarMessage(res.error || 'Failed to remove avatar.');
      }
    } catch (err: any) {
      setAvatarUploadStatus('error');
      setAvatarMessage(err?.response?.data?.detail || 'Failed to remove avatar.');
    }
  };

  // Handle Password Change
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentPassword) {
      setPasswordStatus('error');
      setPasswordMessage('Current password is required.');
      return;
    }
    if (newPassword.length < 8) {
      setPasswordStatus('error');
      setPasswordMessage('New password must be at least 8 characters long.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordStatus('error');
      setPasswordMessage('New passwords do not match.');
      return;
    }

    setPasswordStatus('saving');
    setPasswordMessage('');

    try {
      const res = await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });

      if (res.success) {
        setPasswordStatus('success');
        setPasswordMessage('Password changed successfully. Active sessions updated.');
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
        setTimeout(() => setPasswordStatus('idle'), 4000);
      } else {
        setPasswordStatus('error');
        setPasswordMessage(res.error || 'Failed to change password.');
      }
    } catch (err: any) {
      setPasswordStatus('error');
      setPasswordMessage(err?.response?.data?.detail || 'Current password incorrect or rejected.');
    }
  };

  // Handle Notification Preferences Save
  const handleSaveNotifications = async () => {
    setNotifStatus('saving');
    setNotifMessage('');

    const newPrefs = {
      ...(user.preferences || {}),
      notifications: {
        login_alerts: notifLoginAlerts,
        analysis_complete: notifAnalysisComplete,
        threat_alerts: notifThreatAlerts,
        report_ready: notifReportReady,
      },
    };

    try {
      const res = await authApi.updatePreferences(newPrefs);
      if (res.success && res.data) {
        updateUser(res.data);
        setNotifStatus('success');
        setNotifMessage('Notification preferences persisted successfully.');
        setTimeout(() => setNotifStatus('idle'), 3500);
      } else {
        setNotifStatus('error');
        setNotifMessage(res.error || 'Failed to save notifications.');
      }
    } catch (err: any) {
      setNotifStatus('error');
      setNotifMessage(err?.response?.data?.detail || 'Error saving notification preferences.');
    }
  };

  // Handle Interface Preferences Save
  const handleSaveInterface = async () => {
    setInterfaceStatus('saving');
    setInterfaceMessage('');

    const newPrefs = {
      ...(user.preferences || {}),
      interface: {
        reduced_motion: reducedMotion,
        density: interfaceDensity,
        spatial_effects: spatialEffects,
        default_page: defaultPage,
      },
    };

    try {
      const res = await authApi.updatePreferences(newPrefs);
      if (res.success && res.data) {
        updateUser(res.data);
        setInterfaceStatus('success');
        setInterfaceMessage('Interface preferences updated and saved.');
        setTimeout(() => setInterfaceStatus('idle'), 3500);
      } else {
        setInterfaceStatus('error');
        setInterfaceMessage(res.error || 'Failed to save interface settings.');
      }
    } catch (err: any) {
      setInterfaceStatus('error');
      setInterfaceMessage(err?.response?.data?.detail || 'Error saving interface settings.');
    }
  };

  const currentAvatar = avatarPreview || user.avatar_url;

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-y-auto custom-scrollbar bg-slate-50 text-slate-800 p-4 sm:p-6 lg:p-8">
      <div className="max-w-6xl mx-auto w-full space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-5 border-b border-slate-200 gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-accent text-[22px]">settings</span>
              <h1 className="text-lg font-bold text-slate-900 tracking-wide uppercase font-sans">
                OPERATOR COMMAND HUB
              </h1>
            </div>
            <p className="text-xs text-slate-500 font-mono mt-0.5">
              AUTHENTICATED IDENTITY & SECURITY SETTINGS
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`px-3 py-1 rounded-full font-mono text-[11px] font-semibold uppercase border shadow-2xs ${
                isGoogle
                  ? 'bg-sky-50 border-sky-200 text-sky-700'
                  : 'bg-slate-100 border-slate-300 text-slate-700'
              }`}
            >
              {isGoogle ? 'GOOGLE WORKSPACE OIDC' : 'LOCAL ARGON2ID'}
            </span>
          </div>
        </div>

        {/* Settings Navigation Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 p-1 bg-white border border-slate-200 rounded-xl shadow-2xs">
          <button
            onClick={() => setActiveTab('profile')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs uppercase tracking-wider transition-all ${
              activeTab === 'profile'
                ? 'bg-accent text-white font-bold shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <span className="material-symbols-outlined text-[17px]">account_circle</span>
            Profile
          </button>

          <button
            onClick={() => setActiveTab('security')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs uppercase tracking-wider transition-all ${
              activeTab === 'security'
                ? 'bg-accent text-white font-bold shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <span className="material-symbols-outlined text-[17px]">shield</span>
            Security
          </button>

          <button
            onClick={() => setActiveTab('account')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs uppercase tracking-wider transition-all ${
              activeTab === 'account'
                ? 'bg-accent text-white font-bold shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <span className="material-symbols-outlined text-[17px]">business</span>
            Account & Quota
          </button>

          <button
            onClick={() => setActiveTab('notifications')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs uppercase tracking-wider transition-all ${
              activeTab === 'notifications'
                ? 'bg-accent text-white font-bold shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <span className="material-symbols-outlined text-[17px]">notifications</span>
            Notifications
          </button>

          <button
            onClick={() => setActiveTab('interface')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs uppercase tracking-wider transition-all ${
              activeTab === 'interface'
                ? 'bg-accent text-white font-bold shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <span className="material-symbols-outlined text-[17px]">tune</span>
            Interface
          </button>
        </div>

        {/* TAB 1: PROFILE */}
        {activeTab === 'profile' && (
          <div className="space-y-6">
            {/* Avatar Management Card */}
            <div className="card-3d p-6 bg-white border border-slate-200 rounded-xl space-y-6">
              <div className="border-b border-slate-100 pb-3 flex items-center justify-between">
                <div>
                  <h3 className="font-sans font-bold text-sm text-slate-900 uppercase tracking-wide">
                    Operator Identity & Avatar
                  </h3>
                  <p className="text-xs text-slate-500 font-mono">
                    Official biometric identification displayed across tactical telemetry feeds.
                  </p>
                </div>
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200">
                  TENANT ISOLATED
                </span>
              </div>

              <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
                {/* 3D Interactive Profile Frame */}
                <div className="relative group">
                  <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl bg-gradient-to-br from-sky-50 to-indigo-50 border-2 border-sky-300/80 shadow-md flex items-center justify-center overflow-hidden transform group-hover:scale-105 transition-transform duration-200">
                    {currentAvatar ? (
                      <img
                        src={currentAvatar}
                        alt={user.display_name || user.email}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="text-sky-700 font-mono font-bold text-2xl tracking-wider select-none">
                        {(displayName || user.email).substring(0, 2).toUpperCase()}
                      </div>
                    )}
                  </div>
                  {currentAvatar && (
                    <div className="absolute -top-1.5 -right-1.5 w-6 h-6 rounded-full bg-emerald-500 border-2 border-white flex items-center justify-center shadow-xs">
                      <span className="material-symbols-outlined text-white text-[13px]">check</span>
                    </div>
                  )}
                </div>

                {/* Avatar Actions */}
                <div className="flex-1 space-y-3 text-center sm:text-left">
                  <div className="space-y-1">
                    <h4 className="font-semibold text-slate-900 text-sm">
                      {displayName || user.email.split('@')[0]}
                    </h4>
                    <p className="text-xs text-slate-500 font-mono">
                      Accepts JPEG, PNG, or WebP. Max upload size 2MB. Stored persistently in tenant database.
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center justify-center sm:justify-start gap-3 pt-1">
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileChange}
                      accept="image/jpeg,image/png,image/webp"
                      className="hidden"
                      id="avatar-upload-input"
                    />
                    <label
                      htmlFor="avatar-upload-input"
                      className="cursor-pointer inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 text-white font-mono text-xs uppercase tracking-wide transition-all shadow-sm active:scale-98"
                    >
                      <span className="material-symbols-outlined text-[16px]">photo_camera</span>
                      {currentAvatar ? 'Change Image' : 'Upload Image'}
                    </label>

                    {currentAvatar && (
                      <button
                        type="button"
                        onClick={() => setShowRemoveAvatarConfirm(true)}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-slate-100 hover:bg-red-50 hover:text-red-700 text-slate-600 font-mono text-xs uppercase tracking-wide border border-slate-200 hover:border-red-200 transition-colors"
                      >
                        <span className="material-symbols-outlined text-[16px]">delete</span>
                        Remove Image
                      </button>
                    )}
                  </div>

                  {/* Avatar Upload Feedback Status */}
                  {avatarUploadStatus !== 'idle' && (
                    <div
                      className={`text-xs font-mono p-2.5 rounded-lg border flex items-center gap-2 ${
                        avatarUploadStatus === 'saving'
                          ? 'bg-sky-50 border-sky-200 text-sky-800'
                          : avatarUploadStatus === 'success'
                          ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                          : 'bg-red-50 border-red-200 text-red-800'
                      }`}
                    >
                      <span className="material-symbols-outlined text-[16px] animate-spin">
                        {avatarUploadStatus === 'saving' ? 'refresh' : avatarUploadStatus === 'success' ? 'check_circle' : 'error'}
                      </span>
                      <span>
                        {avatarUploadStatus === 'saving' && 'SAVING: '}
                        {avatarUploadStatus === 'success' && 'SUCCESS: '}
                        {avatarUploadStatus === 'error' && 'ERROR: '}
                        {avatarMessage}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Profile Information Form */}
            <form onSubmit={handleSaveProfile} className="card-3d p-6 bg-white border border-slate-200 rounded-xl space-y-5">
              <div className="border-b border-slate-100 pb-3">
                <h3 className="font-sans font-bold text-sm text-slate-900 uppercase tracking-wide">
                  Operator Credentials
                </h3>
                <p className="text-xs text-slate-500 font-mono">
                  Operational details and identity attributes associated with this command seat.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5 font-mono text-xs">
                <div>
                  <label className="text-slate-600 uppercase text-[11px] font-bold block mb-1.5">
                    Display Name
                  </label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="e.g. Commander Marcus Vance"
                    className="w-full bg-slate-50 border border-slate-200 focus:border-sky-500 focus:bg-white rounded-lg px-3 py-2 text-slate-900 font-sans text-sm focus:outline-none transition-all shadow-2xs"
                  />
                  <span className="text-[10px] text-slate-400 mt-1 block">
                    Visible on incident event signatures and export reports.
                  </span>
                </div>

                <div>
                  <label className="text-slate-600 uppercase text-[11px] font-bold block mb-1.5">
                    Email Address
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="email"
                      value={user.email}
                      disabled
                      className="w-full bg-slate-100 border border-slate-200 rounded-lg px-3 py-2 text-slate-500 font-mono text-xs cursor-not-allowed"
                    />
                    <span className="px-2 py-1 rounded bg-emerald-50 border border-emerald-200 text-emerald-700 text-[10px] font-bold uppercase whitespace-nowrap">
                      VERIFIED
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 mt-1 block">
                    Authoritative primary login identity.
                  </span>
                </div>

                <div>
                  <label className="text-slate-600 uppercase text-[11px] font-bold block mb-1.5">
                    Assigned Organization
                  </label>
                  <input
                    type="text"
                    value={user.organization_name || 'AERION Intelligence Command'}
                    disabled
                    className="w-full bg-slate-100 border border-slate-200 rounded-lg px-3 py-2 text-slate-600 font-mono text-xs cursor-not-allowed"
                  />
                </div>

                <div>
                  <label className="text-slate-600 uppercase text-[11px] font-bold block mb-1.5">
                    Operational Role
                  </label>
                  <div className="flex items-center gap-2 pt-1">
                    <span className="px-3 py-1.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700 font-bold uppercase tracking-wider text-xs">
                      {user.role}
                    </span>
                    <span className="text-slate-400 text-[11px]">Authoritative Access Granted</span>
                  </div>
                </div>
              </div>

              {/* Profile Save Feedback Status */}
              {profileSaveStatus !== 'idle' && (
                <div
                  className={`text-xs font-mono p-3 rounded-lg border flex items-center gap-2 ${
                    profileSaveStatus === 'saving'
                      ? 'bg-sky-50 border-sky-200 text-sky-800'
                      : profileSaveStatus === 'success'
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                      : 'bg-red-50 border-red-200 text-red-800'
                  }`}
                >
                  <span className="material-symbols-outlined text-[17px]">
                    {profileSaveStatus === 'saving' ? 'sync' : profileSaveStatus === 'success' ? 'check_circle' : 'error'}
                  </span>
                  <span>
                    {profileSaveStatus === 'saving' && 'SAVING PROFILE...'}
                    {profileSaveStatus === 'success' && `SUCCESS: ${profileMessage}`}
                    {profileSaveStatus === 'error' && `ERROR: ${profileMessage}`}
                  </span>
                </div>
              )}

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={profileSaveStatus === 'saving'}
                  className="px-5 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-mono text-xs uppercase tracking-wider font-semibold shadow-sm transition-all"
                >
                  {profileSaveStatus === 'saving' ? 'SAVING...' : 'SAVE PROFILE'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* TAB 2: SECURITY */}
        {activeTab === 'security' && (
          <div className="space-y-6">
            {/* Change Password Card */}
            <div className="card-3d p-6 bg-white border border-slate-200 rounded-xl space-y-5">
              <div className="border-b border-slate-100 pb-3 flex items-center justify-between">
                <div>
                  <h3 className="font-sans font-bold text-sm text-slate-900 uppercase tracking-wide">
                    Authentication & Credentials
                  </h3>
                  <p className="text-xs text-slate-500 font-mono">
                    Update your operator password using Argon2id high-entropy salt hashing.
                  </p>
                </div>
                <span className="material-symbols-outlined text-slate-400">key</span>
              </div>

              {isGoogle ? (
                <div className="p-4 bg-sky-50 border border-sky-200 rounded-xl text-xs font-mono text-sky-800 space-y-1">
                  <div className="font-bold flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[18px]">verified_user</span>
                    MANAGED BY GOOGLE ENTERPRISE WORKSPACE
                  </div>
                  <p className="text-sky-700">
                    Your password and multi-factor authentication are authoritatively governed by your Google Workspace organization. Passwords cannot be altered locally.
                  </p>
                </div>
              ) : (
                <form onSubmit={handleChangePassword} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
                    <div>
                      <label className="text-slate-600 uppercase text-[11px] font-bold block mb-1.5">
                        Current Password
                      </label>
                      <input
                        type="password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        placeholder="••••••••••••"
                        className="w-full bg-slate-50 border border-slate-200 focus:border-sky-500 focus:bg-white rounded-lg px-3 py-2 text-slate-900 font-sans text-sm focus:outline-none transition-all shadow-2xs"
                      />
                    </div>

                    <div>
                      <label className="text-slate-600 uppercase text-[11px] font-bold block mb-1.5">
                        New Password
                      </label>
                      <input
                        type="password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        placeholder="••••••••••••"
                        className="w-full bg-slate-50 border border-slate-200 focus:border-sky-500 focus:bg-white rounded-lg px-3 py-2 text-slate-900 font-sans text-sm focus:outline-none transition-all shadow-2xs"
                      />
                    </div>

                    <div>
                      <label className="text-slate-600 uppercase text-[11px] font-bold block mb-1.5">
                        Confirm New Password
                      </label>
                      <input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="••••••••••••"
                        className="w-full bg-slate-50 border border-slate-200 focus:border-sky-500 focus:bg-white rounded-lg px-3 py-2 text-slate-900 font-sans text-sm focus:outline-none transition-all shadow-2xs"
                      />
                    </div>
                  </div>

                  {/* Password Strength Meter */}
                  {newPassword && (
                    <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
                      <div className="flex items-center justify-between text-[11px] font-mono">
                        <span className="text-slate-500 uppercase">Entropy Rating:</span>
                        <span
                          className={`font-bold uppercase ${
                            passwordStrengthScore <= 2
                              ? 'text-red-600'
                              : passwordStrengthScore <= 3
                              ? 'text-amber-600'
                              : 'text-emerald-600'
                          }`}
                        >
                          {passwordStrengthScore <= 2
                            ? 'WEAK'
                            : passwordStrengthScore <= 3
                            ? 'MODERATE'
                            : passwordStrengthScore === 4
                            ? 'STRONG'
                            : 'EXCELLENT'}
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden flex gap-1">
                        {[1, 2, 3, 4, 5].map((level) => (
                          <div
                            key={level}
                            className={`flex-1 h-full rounded-full transition-all ${
                              passwordStrengthScore >= level
                                ? passwordStrengthScore <= 2
                                  ? 'bg-red-500'
                                  : passwordStrengthScore <= 3
                                  ? 'bg-amber-500'
                                  : 'bg-emerald-500'
                                : 'bg-slate-200'
                            }`}
                          />
                        ))}
                      </div>
                      <div className="flex flex-wrap gap-3 text-[10px] font-mono text-slate-500 pt-1">
                        <span className={newPassword.length >= 8 ? 'text-emerald-600 font-semibold' : ''}>
                          ✓ 8+ Characters
                        </span>
                        <span className={/[A-Z]/.test(newPassword) ? 'text-emerald-600 font-semibold' : ''}>
                          ✓ Uppercase Letter
                        </span>
                        <span className={/[0-9]/.test(newPassword) ? 'text-emerald-600 font-semibold' : ''}>
                          ✓ Number
                        </span>
                        <span className={/[^A-Za-z0-9]/.test(newPassword) ? 'text-emerald-600 font-semibold' : ''}>
                          ✓ Special Symbol
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Password Feedback Message */}
                  {passwordStatus !== 'idle' && (
                    <div
                      className={`text-xs font-mono p-3 rounded-lg border flex items-center gap-2 ${
                        passwordStatus === 'saving'
                          ? 'bg-sky-50 border-sky-200 text-sky-800'
                          : passwordStatus === 'success'
                          ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                          : 'bg-red-50 border-red-200 text-red-800'
                      }`}
                    >
                      <span className="material-symbols-outlined text-[17px]">
                        {passwordStatus === 'saving' ? 'sync' : passwordStatus === 'success' ? 'check_circle' : 'error'}
                      </span>
                      <span>
                        {passwordStatus === 'saving' && 'SAVING NEW CREDENTIALS...'}
                        {passwordStatus === 'success' && `SUCCESS: ${passwordMessage}`}
                        {passwordStatus === 'error' && `ERROR: ${passwordMessage}`}
                      </span>
                    </div>
                  )}

                  <div className="flex justify-end pt-1">
                    <button
                      type="submit"
                      disabled={passwordStatus === 'saving'}
                      className="px-5 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-mono text-xs uppercase tracking-wider font-semibold shadow-sm transition-all"
                    >
                      {passwordStatus === 'saving' ? 'SAVING...' : 'CHANGE PASSWORD'}
                    </button>
                  </div>
                </form>
              )}
            </div>

            {/* Session Management */}
            <div className="card-3d p-6 bg-white border border-slate-200 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-mono text-xs">
              <div>
                <div className="text-slate-900 font-bold uppercase text-sm">
                  TERMINATE COMMAND SESSION
                </div>
                <p className="text-slate-500 text-[11px] mt-0.5">
                  Securely revoke current JWT authorization token and return to authentication portal.
                </p>
              </div>

              <button
                onClick={() => setShowLogoutConfirm(true)}
                className="px-4 py-2 rounded-lg bg-red-50 hover:bg-red-100 border border-red-200 text-red-700 font-semibold transition-colors uppercase whitespace-nowrap self-start sm:self-auto"
              >
                Sign Out
              </button>
            </div>
          </div>
        )}

        {/* TAB 3: ACCOUNT & QUOTA */}
        {activeTab === 'account' && (
          <div className="space-y-6">
            {/* Identity & Tenant Metadata */}
            <div className="card-3d p-6 bg-white border border-slate-200 rounded-xl space-y-4 font-mono text-xs">
              <div className="flex justify-between items-center pb-3 border-b border-slate-100">
                <span className="text-slate-900 font-bold uppercase text-sm">
                  TENANT & PLATFORM METADATA
                </span>
                <span className="px-2.5 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 uppercase font-bold text-[10px]">
                  ISOLATION ACTIVE
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="text-slate-500 uppercase text-[10px] block mb-1">
                    Operator User UUID
                  </span>
                  <span className="text-slate-800 bg-slate-50 px-2.5 py-1.5 rounded-md border border-slate-200 block break-all font-mono">
                    {user.id}
                  </span>
                </div>

                <div>
                  <span className="text-slate-500 uppercase text-[10px] block mb-1">
                    Tenant Organization UUID
                  </span>
                  <span className="text-slate-800 bg-slate-50 px-2.5 py-1.5 rounded-md border border-slate-200 block break-all font-mono">
                    {(user as any).organization_id || '00000000-0000-0000-0000-000000000001'}
                  </span>
                </div>

                <div>
                  <span className="text-slate-500 uppercase text-[10px] block mb-1">
                    Session Heartbeat Status
                  </span>
                  <span className="text-emerald-600 font-semibold flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    ACTIVE & AUTHENTICATED
                  </span>
                </div>

                <div>
                  <span className="text-slate-500 uppercase text-[10px] block mb-1">
                    Account Registration Date
                  </span>
                  <span className="text-slate-700">
                    {user.created_at ? new Date(user.created_at).toUTCString() : 'Authoritative System Account'}
                  </span>
                </div>
              </div>
            </div>

            {/* Plan & Entitlement Overview */}
            <div className="card-3d p-6 bg-white border border-slate-200 rounded-xl space-y-4 font-mono text-xs">
              <div className="flex justify-between items-center pb-3 border-b border-slate-100">
                <span className="text-slate-900 font-bold uppercase text-sm">
                  SUBSCRIPTION & QUOTA TIER
                </span>
                <span className="px-3 py-1 rounded-full bg-sky-50 border border-sky-200 text-sky-700 uppercase font-bold text-[11px]">
                  {usage?.tier || 'ENTERPRISE OPERATOR'}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">API Inferences</span>
                  <span className="text-slate-900 text-base font-bold">
                    {isLoadingUsage ? '--' : `${usage?.api_requests_used ?? 0} / ${usage?.api_requests_limit ?? 5000}`}
                  </span>
                </div>
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Drone Flight Min</span>
                  <span className="text-slate-900 text-base font-bold">
                    {isLoadingUsage ? '--' : `${usage?.drone_processing_minutes_used ?? 0} / ${usage?.drone_processing_minutes_limit ?? 600}`}
                  </span>
                </div>
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Satellite Scenes</span>
                  <span className="text-slate-900 text-base font-bold">
                    {isLoadingUsage ? '--' : `${usage?.satellite_scenes_used ?? 0} / ${usage?.satellite_scenes_limit ?? 150}`}
                  </span>
                </div>
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Encrypted Storage</span>
                  <span className="text-slate-900 text-base font-bold">
                    {isLoadingUsage ? '--' : `${((usage?.storage_bytes_used || 0) / 1e6).toFixed(1)} MB`}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: NOTIFICATIONS */}
        {activeTab === 'notifications' && (
          <div className="card-3d p-6 bg-white border border-slate-200 rounded-xl space-y-6">
            <div className="border-b border-slate-100 pb-3">
              <h3 className="font-sans font-bold text-sm text-slate-900 uppercase tracking-wide">
                Operational Alert Notifications
              </h3>
              <p className="text-xs text-slate-500 font-mono">
                Configure real-time telemetry dispatch and incident event triggers for this operator.
              </p>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Security & Login Alerts</div>
                  <div className="text-xs text-slate-500 font-mono">
                    Receive alert pings when a new command session or token renewal occurs.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setNotifLoginAlerts(!notifLoginAlerts)}
                  className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors ${
                    notifLoginAlerts ? 'bg-sky-600 justify-end' : 'bg-slate-300 justify-start'
                  }`}
                >
                  <div className="bg-white w-4 h-4 rounded-full shadow-md"></div>
                </button>
              </div>

              <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Analysis Completion Notifications</div>
                  <div className="text-xs text-slate-500 font-mono">
                    Immediate banner and audio notification upon multi-spectral inference completion.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setNotifAnalysisComplete(!notifAnalysisComplete)}
                  className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors ${
                    notifAnalysisComplete ? 'bg-sky-600 justify-end' : 'bg-slate-300 justify-start'
                  }`}
                >
                  <div className="bg-white w-4 h-4 rounded-full shadow-md"></div>
                </button>
              </div>

              <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Critical Threat & Failure Alerts</div>
                  <div className="text-xs text-slate-500 font-mono">
                    High-priority dispatch when sensor errors or high-confidence breaches occur.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setNotifThreatAlerts(!notifThreatAlerts)}
                  className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors ${
                    notifThreatAlerts ? 'bg-sky-600 justify-end' : 'bg-slate-300 justify-start'
                  }`}
                >
                  <div className="bg-white w-4 h-4 rounded-full shadow-md"></div>
                </button>
              </div>

              <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Situation Report Generation</div>
                  <div className="text-xs text-slate-500 font-mono">
                    Notification when an automated multi-agency situation brief is compiled.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setNotifReportReady(!notifReportReady)}
                  className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors ${
                    notifReportReady ? 'bg-sky-600 justify-end' : 'bg-slate-300 justify-start'
                  }`}
                >
                  <div className="bg-white w-4 h-4 rounded-full shadow-md"></div>
                </button>
              </div>
            </div>

            {/* Notification Feedback Status */}
            {notifStatus !== 'idle' && (
              <div
                className={`text-xs font-mono p-3 rounded-lg border flex items-center gap-2 ${
                  notifStatus === 'saving'
                    ? 'bg-sky-50 border-sky-200 text-sky-800'
                    : notifStatus === 'success'
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                    : 'bg-red-50 border-red-200 text-red-800'
                }`}
              >
                <span className="material-symbols-outlined text-[17px]">
                  {notifStatus === 'saving' ? 'sync' : notifStatus === 'success' ? 'check_circle' : 'error'}
                </span>
                <span>
                  {notifStatus === 'saving' && 'SAVING PREFERENCES...'}
                  {notifStatus === 'success' && `SUCCESS: ${notifMessage}`}
                  {notifStatus === 'error' && `ERROR: ${notifMessage}`}
                </span>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={handleSaveNotifications}
                disabled={notifStatus === 'saving'}
                className="px-5 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-mono text-xs uppercase tracking-wider font-semibold shadow-sm transition-all"
              >
                {notifStatus === 'saving' ? 'SAVING...' : 'SAVE NOTIFICATION PREFERENCES'}
              </button>
            </div>
          </div>
        )}

        {/* TAB 5: INTERFACE */}
        {activeTab === 'interface' && (
          <div className="card-3d p-6 bg-white border border-slate-200 rounded-xl space-y-6">
            <div className="border-b border-slate-100 pb-3">
              <h3 className="font-sans font-bold text-sm text-slate-900 uppercase tracking-wide">
                Spatial & Interface Calibration
              </h3>
              <p className="text-xs text-slate-500 font-mono">
                Tune visual depth, perspective animations, and default operational landing workspaces.
              </p>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Reduced Motion Mode</div>
                  <div className="text-xs text-slate-500 font-mono">
                    Minimizes 3D parallax, transforms, and transitions for accessibility and performance.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setReducedMotion(!reducedMotion)}
                  className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors ${
                    reducedMotion ? 'bg-sky-600 justify-end' : 'bg-slate-300 justify-start'
                  }`}
                >
                  <div className="bg-white w-4 h-4 rounded-full shadow-md"></div>
                </button>
              </div>

              <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <div className="text-sm font-semibold text-slate-900">3D Depth & Particle Dynamics</div>
                  <div className="text-xs text-slate-500 font-mono">
                    Enables spatial particle layers, orbital grids, and card elevation tilts.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSpatialEffects(!spatialEffects)}
                  className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors ${
                    spatialEffects ? 'bg-sky-600 justify-end' : 'bg-slate-300 justify-start'
                  }`}
                >
                  <div className="bg-white w-4 h-4 rounded-full shadow-md"></div>
                </button>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200 gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">UI Telemetry Density</div>
                  <div className="text-xs text-slate-500 font-mono">
                    Adjust spacing and information density across command dashboards.
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setInterfaceDensity('comfortable')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono uppercase tracking-wider font-semibold border ${
                      interfaceDensity === 'comfortable'
                        ? 'bg-sky-600 text-white border-sky-600 shadow-2xs'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    Comfortable
                  </button>
                  <button
                    type="button"
                    onClick={() => setInterfaceDensity('compact')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono uppercase tracking-wider font-semibold border ${
                      interfaceDensity === 'compact'
                        ? 'bg-sky-600 text-white border-sky-600 shadow-2xs'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    Compact
                  </button>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200 gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Default Workspace Landing</div>
                  <div className="text-xs text-slate-500 font-mono">
                    Initial operational interface loaded after authentication.
                  </div>
                </div>
                <select
                  value={defaultPage}
                  onChange={(e) => setDefaultPage(e.target.value)}
                  className="bg-white border border-slate-200 rounded-lg px-3 py-1.5 font-mono text-xs text-slate-900 focus:outline-none focus:border-sky-500 shadow-2xs"
                >
                  <option value="/border">Border Surveillance (/border)</option>
                  <option value="/disaster">Disaster Workspace (/disaster)</option>
                  <option value="/image">Image Perception (/image)</option>
                </select>
              </div>
            </div>

            {/* Interface Feedback Status */}
            {interfaceStatus !== 'idle' && (
              <div
                className={`text-xs font-mono p-3 rounded-lg border flex items-center gap-2 ${
                  interfaceStatus === 'saving'
                    ? 'bg-sky-50 border-sky-200 text-sky-800'
                    : interfaceStatus === 'success'
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                    : 'bg-red-50 border-red-200 text-red-800'
                }`}
              >
                <span className="material-symbols-outlined text-[17px]">
                  {interfaceStatus === 'saving' ? 'sync' : interfaceStatus === 'success' ? 'check_circle' : 'error'}
                </span>
                <span>
                  {interfaceStatus === 'saving' && 'SAVING SETTINGS...'}
                  {interfaceStatus === 'success' && `SUCCESS: ${interfaceMessage}`}
                  {interfaceStatus === 'error' && `ERROR: ${interfaceMessage}`}
                </span>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={handleSaveInterface}
                disabled={interfaceStatus === 'saving'}
                className="px-5 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-mono text-xs uppercase tracking-wider font-semibold shadow-sm transition-all"
              >
                {interfaceStatus === 'saving' ? 'SAVING...' : 'SAVE INTERFACE PREFERENCES'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Remove Avatar Confirmation Modal */}
      {showRemoveAvatarConfirm && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-xl font-mono text-xs">
            <div className="flex items-center gap-3 text-amber-600">
              <span className="material-symbols-outlined text-[24px]">delete</span>
              <h3 className="text-slate-900 font-bold text-sm uppercase">Remove Profile Avatar</h3>
            </div>
            <p className="text-slate-600 text-[11px] leading-relaxed">
              Are you sure you want to remove your operator avatar? The interface will revert to your two-letter identifier initials.
            </p>
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowRemoveAvatarConfirm(false)}
                className="px-3.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-mono transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmRemoveAvatar}
                className="px-3.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-mono shadow-sm transition-colors"
              >
                Confirm Remove
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Logout Confirmation Dialog */}
      {showLogoutConfirm && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-xl font-mono text-xs">
            <div className="flex items-center gap-3 text-amber-600">
              <span className="material-symbols-outlined text-[24px]">warning</span>
              <h3 className="text-slate-900 font-bold text-sm uppercase">Confirm Sign Out</h3>
            </div>
            <p className="text-slate-600 text-[11px] leading-relaxed">
              Are you sure you want to end your operational command session? All active tracking state will be safely terminated.
            </p>
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="px-3.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-mono transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowLogoutConfirm(false);
                  logout();
                }}
                className="px-3.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-mono shadow-sm transition-colors"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
