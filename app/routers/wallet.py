from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import handle_exceptions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.wallet import (
    WalletRead,
    WalletTransactionRead,
    WithdrawalRequest,
)
from app.services.transaction import WithdrawalService
from app.services.wallet import WalletService

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=ApiResponse[WalletRead])
@handle_exceptions
async def get_wallet(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wallet = await WalletService(db).get_or_create(current_user.id)
    return ApiResponse(data=WalletRead.model_validate(wallet))


@router.get("/transactions", response_model=ApiResponse[list[WalletTransactionRead]])
@handle_exceptions
async def list_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    txs = await WalletService(db).list_transactions(current_user.id)
    return ApiResponse(data=[WalletTransactionRead.model_validate(t) for t in txs])


@router.post("/withdraw", response_model=ApiResponse[WalletTransactionRead])
@handle_exceptions
async def request_withdrawal(
    body: WithdrawalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tx = await WithdrawalService(db).request(current_user.id, body.amount, body.phone)
    return ApiResponse(
        message="Demande de retrait enregistrée",
        data=WalletTransactionRead.model_validate(tx),
    )
