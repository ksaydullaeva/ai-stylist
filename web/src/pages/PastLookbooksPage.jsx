import React from 'react';
import { api } from '../api';

const LookCard = ({ outfit, api, handleDelete }) => {
    const [selectedItem, setSelectedItem] = React.useState(null);

    const anchorItemLabel = `Your item - ${typeof outfit.attributes?.color === 'object'
        ? Object.values(outfit.attributes.color).join(', ')
        : (outfit.attributes?.color || '')} ${typeof outfit.attributes?.category === 'object'
            ? Object.values(outfit.attributes.category).join(' ')
            : (outfit.attributes?.category || 'Item')}`;

    return (
        <div className="look-card saved-look-card">
            <div className="look-header-info">
                <button
                    className="btn-delete-outfit"
                    onClick={(e) => handleDelete(outfit.id, e)}
                    title="Delete this look"
                >
                    &times;
                </button>
                <h3 className="look-title">{outfit.style_title}</h3>
                <p className="look-occasion">{outfit.occasion}</p>
                {outfit.created_at && (
                    <p className="look-date">
                        {new Date(outfit.created_at).toLocaleDateString(undefined, {
                            dateStyle: 'medium',
                        })}
                    </p>
                )}
            </div>

            <div className="look-card-visual">
                <div className="look-card-img-wrap">
                    {outfit.try_on_image_url ? (
                        <img
                            src={api.imageUrl(outfit.try_on_image_url)}
                            alt={`Try-on: ${outfit.style_title}`}
                            className="look-card-img"
                        />
                    ) : (
                        <div className="look-card-placeholder">
                            <span>No try-on yet</span>
                        </div>
                    )}
                </div>
            </div>

            <div className="look-card-info">
                {outfit.style_notes && (
                    <div className="look-notes-section">
                        <span className="suggestions-label">Stylist Notes:</span>
                        <p className="look-notes">{outfit.style_notes}</p>
                    </div>
                )}

                <div className="suggestions-container">
                    <span className="suggestions-label">Pairs well with:</span>
                    <div className="look-items-list">
                        {/* Anchor Item */}
                        <div
                            className={`look-item-row anchor-item-row ${selectedItem === 'anchor' ? 'active' : ''}`}
                            onClick={() => setSelectedItem(selectedItem === 'anchor' ? null : 'anchor')}
                        >
                            <div className="look-item-thumb-small">
                                {outfit.source_image_url ? (
                                    <img src={api.imageUrl(outfit.source_image_url)} alt="Your Item" />
                                ) : (
                                    <div className="look-item-placeholder" />
                                )}
                            </div>
                            <div className="look-item-details">
                                <span className="look-item-name">{anchorItemLabel}</span>
                                <p className="look-item-desc">The anchor for this look.</p>
                            </div>
                        </div>

                        {outfit.items?.map((item, j) => (
                            <div
                                key={j}
                                className={`look-item-row ${selectedItem === j ? 'active' : ''}`}
                                onClick={() => setSelectedItem(selectedItem === j ? null : j)}
                            >
                                <div className="look-item-thumb-small">
                                    {item.image_url ? (
                                        <img src={api.imageUrl(item.image_url)} alt={item.category} />
                                    ) : (
                                        <div className="look-item-placeholder" />
                                    )}
                                </div>
                                <div className="look-item-details">
                                    <span className="look-item-name">
                                        {item.color || ''} {item.type || item.category || 'Item'}
                                    </span>
                                    {item.enrichment && <p className="look-item-desc">{item.enrichment}</p>}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Details Area (Visible on Click for deeper notes if any) */}
                    {selectedItem !== null && (
                        <div className="item-details-expansion">
                            {selectedItem === 'anchor' ? (
                                <>
                                    <span className="look-item-name">{anchorItemLabel}</span>
                                    <p className="look-item-desc">Based on the item you uploaded.</p>
                                </>
                            ) : (
                                <>
                                    <span className="look-item-name">
                                        {outfit.items[selectedItem].color || ''} {outfit.items[selectedItem].type || outfit.items[selectedItem].category || 'Item'}
                                    </span>
                                    {outfit.items[selectedItem].enrichment && (
                                        <p className="look-item-desc">{outfit.items[selectedItem].enrichment}</p>
                                    )}
                                </>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default function PastLookbooksPage({ savedOutfits, onBack, onDeleted }) {
    const handleDelete = async (id, e) => {
        e.stopPropagation();
        if (!window.confirm('Are you sure you want to delete this look?')) return;
        try {
            await api.deleteOutfit(id);
            if (onDeleted) onDeleted();
        } catch (err) {
            alert('Failed to delete: ' + err.message);
        }
    };

    return (
        <section className="saved-outfits-section">
            <div className="lookbook-header">
                <div className="lookbook-header-left">
                    <button type="button" className="btn-back-arrow" onClick={onBack} title="Back">
                        &larr;
                    </button>
                    <h2 className="lookbook-title">Saved looks</h2>
                </div>
                <div className="lookbook-controls">
                    <button
                        type="button"
                        className="btn-delete-outfit-all"
                        onClick={async () => {
                            if (window.confirm('Delete ALL saved looks? This cannot be undone.')) {
                                try {
                                    await api.deleteAllOutfits();
                                    if (onDeleted) onDeleted();
                                } catch (err) {
                                    alert('Failed: ' + err.message);
                                }
                            }
                        }}
                    >
                        Clear All
                    </button>
                </div>
            </div>
            {savedOutfits.length === 0 ? (
                <p className="saved-outfits-empty">No saved looks yet. Create a lookbook and use “Save look” on any outfit to add it here.</p>
            ) : (
                <div className="masonry-grid">
                    {savedOutfits.map((outfit) => (
                        <LookCard key={outfit.id} outfit={outfit} api={api} handleDelete={handleDelete} />
                    ))}
                </div>
            )}
        </section>
    );
}
