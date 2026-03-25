import React, { useState, useEffect } from 'react';
import { api } from '../api';

const HangerIcon = () => (
    <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v2m0 0a2 2 0 0 0-2 2v1h4V6a2 2 0 0 0-2-2zM4 19l8-12 8 12H4z" />
    </svg>
);

const PersonIcon = () => (
    <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
    </svg>
);

const ChangeIcon = () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
        <path d="M3 3v5h5" />
    </svg>
);

export default function StudioPage({
    preview,
    userPhotoPreview,
    userPhoto,
    onFileChange,
    onUserPhotoChange,
    onRemoveItem,
    onRemoveUserPhoto,
    runPipeline,
    loading,
    file,
    error
}) {
    const hasItem = !!file;
    const hasModel = !!userPhoto;

    const [validatingItem, setValidatingItem] = useState(false);
    const [validatingUser, setValidatingUser] = useState(false);
    const validating = validatingItem || validatingUser;

    const [itemValidation, setItemValidation] = useState(null);
    const [userValidation, setUserValidation] = useState(null);

    // Reset validations when the corresponding upload changes
    useEffect(() => {
        setItemValidation(null);
    }, [file]);

    useEffect(() => {
        setUserValidation(null);
    }, [userPhoto]);

    // Step 1 validation only (runs only when item + full-body photo exist).
    // This prevents re-validating Step 2 when you change only the item.
    useEffect(() => {
        if (!file || !userPhoto) return;
        if (validatingItem) return;
        setValidatingItem(true);
        api.validateItem(file)
            .then((res) => setItemValidation(res))
            .catch(() => setItemValidation({
                item_ok: false,
                item_error: 'validation_failed',
                item_message: 'Validation failed.'
            }))
            .finally(() => setValidatingItem(false));
    }, [file, userPhoto]);

    // Step 2 validation only (runs when the full-body photo changes).
    // This prevents re-validating Step 2 when you change only the item.
    useEffect(() => {
        if (!userPhoto) return;
        if (validatingUser) return;
        setValidatingUser(true);
        api.validateUserPhoto(userPhoto)
            .then((res) => setUserValidation(res))
            .catch(() => setUserValidation({
                user_ok: false,
                user_error: 'validation_failed',
                user_message: 'Validation failed.'
            }))
            .finally(() => setValidatingUser(false));
    }, [userPhoto]);

    const handleSkip = async () => {
        if (!file || validating) return;
        setValidatingItem(true);
        try {
            await api.analyze(file);
            setItemValidation({ item_ok: true, item_message: null });
            runPipeline();
        } catch (err) {
            setItemValidation({
                item_ok: false,
                item_error: 'analysis_failed',
                item_message: err?.message || 'The image does not appear to contain a clothing item.'
            });
        } finally {
            setValidatingItem(false);
        }
    };

    const handleBackToItemStep = () => {
        // "Back" from Step 2 (waiting on full-body photo) -> Step 1 (clothing item upload).
        if (loading || validating) return;
        onRemoveItem();
    };

    const validatedItem = itemValidation && itemValidation.item_ok;
    const validatedUser = userValidation && userValidation.user_ok;
    const validatedPair = hasItem && hasModel && validatedItem && validatedUser;

    const itemFailedNoModel = itemValidation && !itemValidation.item_ok;
    const itemFailedPair = itemValidation && hasItem && hasModel && !itemValidation.item_ok;
    const userFailedPair = userValidation && hasItem && hasModel && !userValidation.user_ok;
    const swapLikely = itemFailedPair && userFailedPair;
    const validationFailed = hasItem && hasModel && itemValidation && userValidation && !validatedPair;
    const showPairedPreview = hasItem && hasModel && validatedPair;
    const canCreate = hasItem && !validating && (!hasModel || validatedPair);
    const checkingDone = validatedPair;
    const activeStep = !hasItem ? 1 : (validating || checkingDone) ? 3 : 2;

    // Each step is independently done based on its own data, not just activeStep position.
    // This means clicking "Change" on one step leaves the other steps' indicators untouched.
    // While validating, avoid showing step "done" checkmarks early (parallel async validations).
    // Only show "done" after validation completes for the relevant step.
    const step1Done = hasItem && (!hasModel ? true : !validating && !!itemValidation?.item_ok);
    const step2Done = (!hasModel && activeStep >= 3) || (hasModel && !validating && !!userValidation?.user_ok);
    const step3Done = checkingDone;

    return (
        <section className="studio-container studio-container-sequential tcm-studio-shell">
            <div className="tcm-studio-card">
                <div className="tcm-stepper">
                    <div className={`tcm-step ${(step1Done || activeStep >= 1) ? 'active' : ''} ${step1Done ? 'done' : ''}`}>
                        <span className="tcm-step-dot">{step1Done ? '✓' : '1'}</span>
                        <span>Clothing Item</span>
                    </div>
                    <div className={`tcm-step ${(step2Done || activeStep >= 2) ? 'active' : ''} ${step2Done ? 'done' : ''}`}>
                        <span className="tcm-step-dot">{step2Done ? '✓' : '2'}</span>
                        <span>Full-body Image</span>
                    </div>
                    <div className={`tcm-step ${(step3Done || activeStep >= 3) ? 'active' : ''} ${step3Done ? 'done' : ''}`}>
                        <span className="tcm-step-dot">{step3Done ? '✓' : '3'}</span>
                        <span>Checking</span>
                    </div>
                </div>

                {validating && hasItem && (
                    <div className="upload-validating tcm-checking-state">
                        <div className="upload-validating-icons">
                            <span className="upload-validating-icon upload-validating-icon-item">
                                <HangerIcon />
                            </span>
                            <span className="upload-validating-icon upload-validating-icon-model">
                                <PersonIcon />
                            </span>
                        </div>
                        <span className="upload-validating-text">Checking your photos</span>
                        <span className="upload-validating-dots">...</span>
                        <div className="upload-validating-bar" />
                    </div>
                )}

                {!validating && !showPairedPreview && !hasItem && (
                    <>
                        <div className="dropzone tcm-dropzone" onClick={() => document.getElementById('item-input').click()}>
                            <input id="item-input" type="file" className="hidden" accept="image/*" onChange={onFileChange} />
                            <HangerIcon />
                            <span className="dropzone-text">Drop the item you want to style.</span>
                            <span className="tcm-dropzone-hint">
                                Upload a photo where only ONE garment is visible. Use a plain background, good lighting, and make sure the full garment is visible.
                            </span>
                            <span className="tcm-dropzone-hint">JPEG, JPG, and PNG formats, up to 5 MB</span>
                        </div>
                        <button className="btn-primary tcm-main-btn" type="button" disabled>
                            Next
                        </button>
                    </>
                )}

                {!validating && !showPairedPreview && hasItem && !hasModel && (
                    <>
                        <div style={{ width: '100%', maxWidth: 500, display: 'flex', justifyContent: 'flex-start' }}>
                            <button
                                type="button"
                                className="btn-back-arrow"
                                onClick={handleBackToItemStep}
                                aria-label="Back to Clothing Item step"
                                disabled={loading || validating}
                            >
                                &larr;
                            </button>
                        </div>
                        {itemFailedNoModel && itemValidation?.item_message && (
                            <div className="banner error" style={{ width: '100%', marginBottom: 0 }}>{itemValidation.item_message}</div>
                        )}
                        {!itemFailedNoModel && (
                            <div className="dropzone tcm-dropzone" onClick={() => document.getElementById('user-input').click()}>
                                <input id="user-input" type="file" className="hidden" accept="image/*" onChange={onUserPhotoChange} />
                                <PersonIcon />
                                <span className="dropzone-text">Drop a full-body photo of yourself.</span>
                                <span className="tcm-dropzone-hint">
                                    Head-to-toe, face visible, stand straight. Please remove coats/heavy winter layers.
                                </span>
                                <span className="tcm-dropzone-hint">JPEG, JPG, and PNG formats, up to 5 MB</span>
                            </div>
                        )}
                        <button className="btn-secondary tcm-main-btn tcm-skip-btn" type="button" onClick={handleSkip} disabled={!canCreate || loading}>
                            Skip section and generate
                        </button>
                    </>
                )}

                {!validating && !showPairedPreview && hasItem && hasModel && validationFailed && (itemFailedPair || userFailedPair) && (
                    <div className="upload-received">
                        {swapLikely && (
                            <p className="banner error" style={{ marginBottom: 8 }}>
                                Your uploads look swapped/reversed. Please upload the garment/product image for <b>Clothing Item</b> (Step 1)
                                and your full-body photo for <b>Full-body Image</b> (Step 2).
                            </p>
                        )}
                        {itemFailedPair && itemValidation?.item_message && (
                            <p className="banner error" style={{ marginBottom: 8 }}>{itemValidation.item_message}</p>
                        )}
                        {userFailedPair && userValidation?.user_message && (
                            <p className="banner error" style={{ marginBottom: 8 }}>
                                {userValidation.user_message}
                            </p>
                        )}
                        {itemFailedPair && (
                            <div className="dropzone tcm-dropzone" onClick={() => document.getElementById('item-input').click()}>
                                <input id="item-input" type="file" className="hidden" accept="image/*" onChange={onFileChange} />
                                <HangerIcon />
                                <span className="dropzone-text">Drop the item you want to style.</span>
                                <span className="tcm-dropzone-hint">
                                    Upload a photo where only ONE garment is visible (not a full outfit). Use a plain background, good lighting, and make sure the full garment is visible.
                                </span>
                                <span className="tcm-dropzone-hint">JPEG, JPG, and PNG formats, up to 5 MB</span>
                            </div>
                        )}
                        {userFailedPair && (
                            <div className="dropzone tcm-dropzone" onClick={() => document.getElementById('user-input').click()}>
                                <input id="user-input" type="file" className="hidden" accept="image/*" onChange={onUserPhotoChange} />
                                <PersonIcon />
                                <span className="dropzone-text">Drop a full-body photo of yourself.</span>
                                <span className="tcm-dropzone-hint">
                                    Head-to-toe only, face visible, stand straight. Please remove coats/heavy winter layers.
                                </span>
                                <span className="tcm-dropzone-hint">JPEG, JPG, and PNG formats, up to 5 MB</span>
                            </div>
                        )}
                    </div>
                )}

                {showPairedPreview && (
                    <>
                        <div className="studio-images-side-by-side tcm-preview-grid">
                            <div className="studio-image-block tcm-preview-card">
                                <div className="studio-image-wrap">
                                    <img src={preview} alt="Your item" className="studio-image-img" />
                                </div>
                                <button type="button" className="upload-received-change tcm-change-btn" onClick={onRemoveItem}>
                                    <ChangeIcon /> Change
                                </button>
                            </div>
                            <div className="studio-image-block tcm-preview-card">
                                <div className="studio-image-wrap">
                                    <img src={userPhotoPreview} alt="You" className="studio-image-img" />
                                </div>
                                <button type="button" className="upload-received-change tcm-change-btn" onClick={onRemoveUserPhoto}>
                                    <ChangeIcon /> Change
                                </button>
                            </div>
                        </div>
                        <button className="btn-primary tcm-main-btn" onClick={runPipeline} disabled={loading}>
                            Create Your Look
                        </button>
                    </>
                )}

                {error && <div className="banner error" style={{ width: '100%', marginBottom: 0 }}>{error}</div>}
            </div>
        </section>
    );
}
