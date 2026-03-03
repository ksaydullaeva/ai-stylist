from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from core.database import Base


class Outfit(Base):
    __tablename__ = "outfits"

    id = Column(Integer, primary_key=True, index=True)
    occasion = Column(String(100), nullable=False)
    style_title = Column(String(255), nullable=False)
    style_notes = Column(Text)
    color_palette = Column(JSONB)
    source_image_path = Column(String(512))
    attributes = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("OutfitItem", back_populates="outfit", cascade="all, delete-orphan")


class OutfitItem(Base):
    __tablename__ = "outfit_items"

    id = Column(Integer, primary_key=True, index=True)
    outfit_id = Column(ForeignKey("outfits.id"), nullable=False)
    category = Column(String(100))
    color = Column(String(100))
    type = Column(String(100))
    description = Column(Text)
    shopping_keywords = Column(String(512))
    image_path = Column(String(512))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    outfit = relationship("Outfit", back_populates="items")
