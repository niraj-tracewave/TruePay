def get_otp_message(otp: str) -> str:
    return (
        f"Hello Customer,\nYour OTP for login is {otp}. "
        f"This OTP is valid for 5 minutes. "
        f"Please do not share it with anyone.\nTRACEWAVE##"
    )


def get_loan_approval_message(loan_id: str, amount: float) -> str:
    return (
        f"Dear Customer,\nYour loan with ID {loan_id} for ₹{amount:.2f} has been approved. "
        f"Thank you for choosing us!\nTRACEWAVE##"
    )
