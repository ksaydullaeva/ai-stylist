import React from 'react';
import { api } from '../api';

const HangerIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="tryon-loading-icon-svg">
        <path d="M12 3a2 2 0 0 1 2 2c0 .97-.55 1.79-1.35 2.22L20 12H4l7.35-4.78A2.26 2.26 0 0 1 10 5a2 2 0 0 1 2-2Z" />
        <path d="M4 12c-1.1 0-2 .9-2 2s.9 2 2 2h16c1.1 0 2-.9 2-2s-.9-2-2-2" />
    </svg>
);

const SparkleIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="tryon-loading-icon-svg">
        <path d="M12 3v3M12 18v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M3 12h3M18 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12" />
    </svg>
);

const PersonIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="tryon-loading-icon-svg">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
    </svg>
);

export default function TryOnModal({ outfit, tryOnLoading, tryOnError, tryOnResultUrl, onClose }) {
    if (!outfit) return null;

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h3>Virtual Try-On</h3>
                    <button className="modal-close" onClick={onClose}>×</button>
                </div>
                <div className="modal-body">
                    {tryOnLoading ? (
                        <div className="tryon-loading-state">
                            <div className="tryon-loading-icons">
                                <span className="tryon-loading-icon tryon-loading-icon-1"><HangerIcon /></span>
                                <span className="tryon-loading-icon tryon-loading-icon-2"><SparkleIcon /></span>
                                <span className="tryon-loading-icon tryon-loading-icon-3"><PersonIcon /></span>
                            </div>
                            <p className="tryon-loading-title">Creating your try-on</p>
                            <p className="tryon-loading-sub">Dressing you in the look…</p>
                            <div className="tryon-loading-bar-wrap">
                                <div className="tryon-loading-bar" />
                            </div>
                        </div>
                    ) : tryOnError ? (
                        <div className="banner error">{tryOnError}</div>
                    ) : (
                        <>
                            <p className="look-occasion" style={{ marginBottom: 0 }}>
                                {outfit.style_title}
                            </p>
                            {tryOnResultUrl ? (
                                <img src={api.imageUrl(tryOnResultUrl)} alt="Try-on result" className="try-on-result-img" />
                            ) : (
                                <div style={{ textAlign: 'center', padding: '40px' }}>
                                    <p>Something went wrong. Please try again.</p>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
