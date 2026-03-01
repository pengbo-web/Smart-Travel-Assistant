from sqlmodel import SQLModel,Field

class User(SQLModel,table=True):
  id:int | None = Field(default=None,primary_key=True,index=True)
  avatar:str = Field(nullable=False)#头像
  nickname:str = Field(nullable=False)#昵称
  openid:str = Field(nullable=False,unique=True,index=True)#openid，微信用户的唯一标识符