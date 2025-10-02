from pydantic import BaseModel

class Package(BaseModel):
    description: str
    days: str
    price: float
   
