import React from 'react';

export default function Header({ onToggleSaved, onReset, savedOutfitsLoading, backendOk }) {
    return (
        <header className="header">
            <h1 className="title title-gradient">Style Studio</h1>
            <p className="tagline">Personalized AI styling for your unique style.</p>
            <div className="header-actions">
                <button
                    type="button"
                    className="tag-pill"
                    onClick={onToggleSaved}
                    disabled={savedOutfitsLoading}
                >
                    {savedOutfitsLoading ? 'Loading…' : 'Saved looks'}
                </button>
                <button type="button" className="tag-pill btn-reset-action" onClick={onReset}>
                    New Session
                </button>
            </div>
            {backendOk === false && (
                <div className="banner error">
                    Offline: Start backend with <code>uvicorn main:app --reload</code>
                </div>
            )}
        </header>
    );
}
