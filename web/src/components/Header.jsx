import React from 'react';

export default function Header({ backendOk, title, tagline }) {
    return (
        <header className="header">
            <h1 className="title title-gradient">{title || 'Clothing Lens'}</h1>
            <p className="tagline">{tagline || 'Upload a clothing photo to find similar items and get directions to the matching store.'}</p>
            {backendOk === false && (
                <div className="banner error">
                    Offline: Start backend with <code>uvicorn main:app --reload</code>
                </div>
            )}
        </header>
    );
}
