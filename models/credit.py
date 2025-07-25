from sqlalchemy import (Column, Integer, String, Float, Enum, UniqueConstraint, Index)

from common.enums import LoanType
from db_domains import CreateUpdateTime, CreateByUpdateBy


class CreditScoreRangeRate(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "credit_score_range_rate"

    id = Column(Integer, primary_key=True, index=True)

    # Credit Score Range fields
    label = Column(String, nullable=False)
    min_score = Column(Integer, nullable=True)
    max_score = Column(Integer, nullable=True)

    # Interest Rate fields
    rate_percentage = Column(Float, nullable=False)
    loan_type = Column(
        Enum(LoanType), default=LoanType.PERSONAL, server_default=LoanType.PERSONAL.value, nullable=False
    )

    __table_args__ = (
        UniqueConstraint('min_score', 'max_score', 'loan_type', name='uq_combined_score_loan'),
        Index('ix_combined_min_score', 'min_score'),
        Index('ix_combined_max_score', 'max_score'),
    )


class ProcessingFee(CreateUpdateTime, CreateByUpdateBy):
    __tablename__ = "processing_fees"

    id = Column(Integer, primary_key=True, index=True)
    rate_percent = Column(Float, nullable=False)
    amount = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('rate_percent', 'amount', name='uq_processing_fee_rate_amount'),
        Index('ix_processing_fee_rate_percent', 'rate_percent'),
        Index('ix_processing_fee_amount', 'amount'),
    )
