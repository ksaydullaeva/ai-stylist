from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Outfit(Base):
    __tablename__ = "outfits"

    id = Column(Integer, primary_key=True, index=True)
    occasion = Column(String(100), nullable=False)
    style_title = Column(String(255), nullable=False)
    style_notes = Column(Text)
    color_palette = Column(String(255))
    source_image_path = Column(String(512))
    attributes = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    images = relationship(
        "OutfitImage",
        back_populates="outfit",
        cascade="all, delete-orphan",
    )
    items = relationship(
        "OutfitItem",
        back_populates="outfit",
        cascade="all, delete-orphan",
    )


class OutfitImage(Base):
    __tablename__ = "outfit_images"

    id = Column(Integer, primary_key=True, index=True)
    outfit_id = Column(ForeignKey("outfits.id"), nullable=False)
    kind = Column(String(50), default="flatlay")
    image_path = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    outfit = relationship("Outfit", back_populates="images")


class OutfitItem(Base):
    __tablename__ = "outfit_items"

    id = Column(Integer, primary_key=True, index=True)
    outfit_id = Column(ForeignKey("outfits.id"), nullable=False)
    category = Column(String(100))
    color = Column(String(100))
    type = Column(String(100))
    description = Column(Text)
    likely_owned = Column(Boolean, default=False)
    shopping_keywords = Column(String(512))
    image_path = Column(String(512))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    outfit = relationship("Outfit", back_populates="items")

