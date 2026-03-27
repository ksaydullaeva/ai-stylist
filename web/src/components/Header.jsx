import React, { useState, useEffect } from 'react';

export default function Header({ backendOk, title, tagline }) {
    const [scrolled, setScrolled] = useState(false);

    useEffect(() => {
        const handleScroll = () => {
            setScrolled(window.scrollY > 10);
        };
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    return (
        <>
            <div className={`top-navbar ${scrolled ? 'scrolled' : ''}`} role="navigation" aria-label="Top">
                <div className="top-navbar-inner">
                    <div className="top-navbar-brand" aria-label="Style Studio">
                        <span className="brand-icon">✨</span>
                        Style Studio
                    </div>
                </div>
            </div>

            <header className="header">
                {title && <h1 className="title title-gradient">{title}</h1>}
                {tagline ? <p className="tagline">{tagline}</p> : null}
                {backendOk === false && (
                    <div className="banner error">
                        Offline: Start backend with <code>uvicorn main:app --reload</code>
                    </div>
                )}
            </header>
        </>
    );
}
