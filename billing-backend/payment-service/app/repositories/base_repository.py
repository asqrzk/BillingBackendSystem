from typing import Generic, TypeVar, Type, List, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
import logging

from app.core.database import Base

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository class with common CRUD operations."""
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def get_by_id(self, id: Any, relationships: List[str] = None) -> Optional[ModelType]:
        """Get a record by ID with optional relationships."""
        try:
            query = select(self.model).where(self.model.id == id)
            
            if relationships:
                for rel in relationships:
                    query = query.options(selectinload(getattr(self.model, rel)))
            
            result = await self.session.execute(query)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting {self.model.__name__} by ID {id}: {e}")
            raise
    
    async def get_all(
        self, 
        offset: int = 0, 
        limit: int = 100, 
        relationships: List[str] = None,
        filters: Dict[str, Any] = None
    ) -> List[ModelType]:
        """Get all records with pagination and optional filtering."""
        try:
            query = select(self.model)
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        query = query.where(getattr(self.model, field) == value)
            
            # Apply relationships
            if relationships:
                for rel in relationships:
                    query = query.options(selectinload(getattr(self.model, rel)))
            
            # Apply pagination
            query = query.offset(offset).limit(limit)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting all {self.model.__name__}: {e}")
            raise
    
    async def count(self, filters: Dict[str, Any] = None) -> int:
        """Count records with optional filtering."""
        try:
            query = select(func.count(self.model.id))
            
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        query = query.where(getattr(self.model, field) == value)
            
            result = await self.session.execute(query)
            return result.scalar()
        except Exception as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            raise
    
    async def create(self, obj_data: Dict[str, Any]) -> ModelType:
        """Create a new record."""
        try:
            db_obj = self.model(**obj_data)
            self.session.add(db_obj)
            await self.session.flush()
            await self.session.refresh(db_obj)
            return db_obj
        except Exception as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            await self.session.rollback()
            raise
    
    async def update(self, id: Any, obj_data: Dict[str, Any]) -> Optional[ModelType]:
        """Update a record by ID."""
        try:
            # Remove None values from update data
            update_data = {k: v for k, v in obj_data.items() if v is not None}
            
            if not update_data:
                return await self.get_by_id(id)
            
            query = update(self.model).where(self.model.id == id).values(**update_data)
            await self.session.execute(query)
            
            return await self.get_by_id(id)
        except Exception as e:
            logger.error(f"Error updating {self.model.__name__} with ID {id}: {e}")
            await self.session.rollback()
            raise
    
    async def delete(self, id: Any) -> bool:
        """Delete a record by ID."""
        try:
            query = delete(self.model).where(self.model.id == id)
            result = await self.session.execute(query)
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting {self.model.__name__} with ID {id}: {e}")
            await self.session.rollback()
            raise
    
    async def get_by_field(self, field: str, value: Any, relationships: List[str] = None) -> Optional[ModelType]:
        """Get a record by a specific field."""
        try:
            if not hasattr(self.model, field):
                raise ValueError(f"Field {field} not found in {self.model.__name__}")
            
            query = select(self.model).where(getattr(self.model, field) == value)
            
            if relationships:
                for rel in relationships:
                    query = query.options(selectinload(getattr(self.model, rel)))
            
            result = await self.session.execute(query)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting {self.model.__name__} by {field}={value}: {e}")
            raise 