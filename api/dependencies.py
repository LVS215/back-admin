from ninja import Query
from typing import Optional

class PaginationParams(Schema):
    page: int = 1
    page_size: int = 10
    
    @property
    def offset(self):
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self):
        return self.page_size

class FilterParams(Schema):
    category: Optional[int] = None
    author: Optional[int] = None
    status: Optional[str] = None
    search: Optional[str] = None
