import React, { useState } from 'react';
import { X } from 'lucide-react';

/**
 * AuthModal — Minimalist editorial modal for user login & registration.
 * Enables persistent audit history across devices and sessions.
 */
export default function AuthModal({ isOpen, onClose, onAuthSuccess }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const endpoint = mode === 'register' ? '/api/auth/register' : '/api/auth/login';
      const payload =
        mode === 'register'
          ? { username: username.trim(), email: email.trim(), password }
          : { username_or_email: (email || username).trim(), password };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Authentication failed. Please check your details.');
      }

      onAuthSuccess(data.access_token, data.user);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="auth-modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
    >
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button
          className="auth-close-btn"
          onClick={onClose}
          aria-label="Close modal"
        >
          <X size={16} strokeWidth={1.8} />
        </button>

        <div className="auth-modal-header">
          <h2 id="auth-modal-title" className="auth-modal-title">
            {mode === 'login' ? 'Sign in to Veritas' : 'Create an account'}
          </h2>
          <p className="auth-modal-sub">
            {mode === 'login'
              ? 'Access your audit history across all devices and sessions.'
              : 'Save and synchronize verified claims in your persistent database.'}
          </p>
        </div>

        <div className="auth-modal-tabs" role="tablist">
          <button
            role="tab"
            aria-selected={mode === 'login'}
            className={`auth-tab-btn ${mode === 'login' ? 'active' : ''}`}
            onClick={() => { setMode('login'); setError(null); }}
          >
            Sign in
          </button>
          <button
            role="tab"
            aria-selected={mode === 'register'}
            className={`auth-tab-btn ${mode === 'register' ? 'active' : ''}`}
            onClick={() => { setMode('register'); setError(null); }}
          >
            Create account
          </button>
        </div>

        {error && (
          <div className="auth-error" role="alert" style={{ marginBottom: 14 }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          {mode === 'register' && (
            <div className="auth-field">
              <label className="auth-label" htmlFor="auth-username">
                Username
              </label>
              <input
                id="auth-username"
                type="text"
                className="auth-input"
                placeholder="editor_jane"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
              />
            </div>
          )}

          <div className="auth-field">
            <label className="auth-label" htmlFor="auth-email">
              {mode === 'register' ? 'Email address' : 'Username or email'}
            </label>
            <input
              id="auth-email"
              type={mode === 'register' ? 'email' : 'text'}
              className="auth-input"
              placeholder={mode === 'register' ? 'jane@veritas.org' : 'Username or email'}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete={mode === 'register' ? 'email' : 'username'}
            />
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="auth-password">
              Password
            </label>
            <input
              id="auth-password"
              type="password"
              className="auth-input"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            />
          </div>

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
      </div>
    </div>
  );
}
