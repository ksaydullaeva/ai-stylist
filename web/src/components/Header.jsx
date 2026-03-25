import React from 'react';

export default function Header({ backendOk }) {
    return (
        <header className="header">
            <h1 className="title title-gradient">Style Studio</h1>
            <p className="tagline">Experience next-level fashion with AI that learns your style and delivers curated looks that truly match you.</p>
            {backendOk === false && (
                <div className="banner error">
                    Offline: Start backend with <code>uvicorn main:app --reload</code>
                </div>
            )}
        </header>
    );
}
