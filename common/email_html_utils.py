from schemas.loan_schemas import LoanForm


def build_loan_email_bodies(loan_application_form: LoanForm, applicant_obj, applicant_id):
    plain_body = (
        f"Information:\n"
        f"A new loan application has been submitted.\n\n"
        f"🧾 Applicant Details:\n"
        f"Name: {loan_application_form.name}\n"
        f"Email: {loan_application_form.email}\n"
        f"Phone: {loan_application_form.phone_number}\n"
        f"Loan UID: {applicant_id}\n"
        f"Desired Loan Amount: ₹{loan_application_form.desired_loan}\n"
        f"Applied At: {applicant_obj.created_at.strftime('%d-%m-%Y %I:%M %p') if applicant_obj.created_at else 'N/A'}\n\n"
        f"Thanks & Regards,\n"
        f"Loan Processing Team"
    )

    html_body = f"""
    <html>
        <body>
            <p>A new loan application has been submitted.</p>
            <h4>Applicant Details:</h4>
            <ul>
                <li><strong>Name:</strong> {loan_application_form.name}</li>
                <li><strong>Email :</strong> {loan_application_form.email}</li>
                <li><strong>Phone:</strong> {loan_application_form.phone_number}</li>
                <li><strong>Loan UID:</strong> {applicant_obj.loan_uid}</li>
                <li><strong>Desired Loan Amount:</strong> ₹{loan_application_form.desired_loan}</li>
                <li><strong>Applied At:</strong> {applicant_obj.created_at.strftime('%d-%m-%Y %I:%M %p') if applicant_obj.created_at else "N/A"} </li>
            </ul>
            <p>Kindly visit the admin panel at <b><a href="https://admin.truepay.co.in/">https://admin.truepay.co.in/</a></b> and review the loan details.</p>
            <p>Thanks & Regards,<br/>TruePay Loan Processing Team</p>
        </body>
    </html>
    """

    return plain_body, html_body
