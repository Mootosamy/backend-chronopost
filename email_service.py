import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from pathlib import Path
from dotenv import load_dotenv
import logging

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

# SMTP Configuration
SMTP_HOST = os.getenv('SMTP_HOST', 'ceinture.o2switch.net')
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
SMTP_USER = os.getenv('SMTP_USER', 'cim.payementprocess@gmail.com')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'cim.payementprocess@gmail.com')
SENDER_NAME = os.getenv('SENDER_NAME', 'Chronopost Mauritius Ltd')

def format_amount(amount: str) -> str:
    """Format amount with comma (Mauritius format)"""
    try:
        # Handle both comma and dot as decimal separator
        amount_str = str(amount).replace(',', '.')
        num = float(amount_str)
        # Format with 2 decimals and replace dot with comma
        formatted = f"{num:.2f}".replace('.', ',')
        # Add space as thousands separator
        parts = formatted.split(',')
        parts[0] = ' '.join([parts[0][max(i, 0):i+3] for i in range(len(parts[0]), 0, -3)][::-1])
        return ','.join(parts)
    except:
        return str(amount)

def create_payment_email_template(payment_data: dict) -> str:
    """Create a professional HTML email template for payment link"""
    
    # Format amount with comma
    formatted_amount = format_amount(payment_data['amount'])
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment Request</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 0;
                background-color: #f4f4f4;
            }}
            .container {{
                background-color: #ffffff;
                margin: 20px auto;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 600;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .greeting {{
                font-size: 18px;
                margin-bottom: 20px;
                color: #2c3e50;
            }}
            .info-box {{
                background-color: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 20px;
                margin: 25px 0;
                border-radius: 4px;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #e9ecef;
            }}
            .info-row:last-child {{
                border-bottom: none;
            }}
            .info-label {{
                font-weight: 600;
                color: #495057;
            }}
            .info-value {{
                color: #212529;
                text-align: right;
            }}
            .amount {{
                font-size: 32px;
                font-weight: bold;
                color: #667eea;
                text-align: center;
                margin: 30px 0;
            }}
            .cta-button {{
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                padding: 16px 40px;
                border-radius: 50px;
                font-size: 16px;
                font-weight: 600;
                text-align: center;
                margin: 30px 0;
                transition: transform 0.3s ease;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            }}
            .cta-container {{
                text-align: center;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 25px;
                text-align: center;
                color: #6c757d;
                font-size: 14px;
                border-top: 1px solid #e9ecef;
            }}
            .security-note {{
                background-color: #e8f5e9;
                border-left: 4px solid #4caf50;
                padding: 15px;
                margin: 25px 0;
                border-radius: 4px;
                font-size: 14px;
            }}
            .link-container {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin: 20px 0;
                word-break: break-all;
                font-family: monospace;
                font-size: 12px;
                color: #495057;
            }}
            @media only screen and (max-width: 600px) {{
                .content {{
                    padding: 20px 15px;
                }}
                .info-row {{
                    flex-direction: column;
                }}
                .info-value {{
                    text-align: left;
                    margin-top: 5px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Payment Request</h1>
            </div>
            
            <div class="content">
                <div class="greeting">
                    Dear {payment_data['client_first_name']} {payment_data['client_last_name']},
                </div>
                
                <p>You have received a payment request from <strong>Chronopost Mauritius Ltd</strong>.</p>
                
                <div class="amount">
                    {payment_data['currency']} {formatted_amount}
                </div>
                
                <div class="info-box">
                    <div class="info-row">
                        <span class="info-label">Order Name:</span>
                        <span class="info-value">{payment_data['order_name']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Order Number:</span>
                        <span class="info-value">{payment_data['order_number']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Reference:</span>
                        <span class="info-value">{payment_data['reference']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Amount:</span>
                        <span class="info-value"><strong>{payment_data['currency']} {formatted_amount}</strong></span>
                    </div>
                </div>
                
                <p>To complete your payment securely, please click the button below:</p>
                
                <div class="cta-container">
                    <a href="{payment_data['payment_link']}" class="cta-button">
                        Pay Now
                    </a>
                </div>
                
                <div class="security-note">
                    <strong>🔒 Secure Payment</strong><br>
                    This is a secure payment link powered by VISA. Your payment information is encrypted and protected.
                </div>
                
                <p style="color: #6c757d; font-size: 14px;">
                    If the button doesn't work, you can copy and paste this link into your browser:
                </p>
                
                <div class="link-container">
                    {payment_data['payment_link']}
                </div>
                
                <p style="margin-top: 30px; color: #6c757d; font-size: 14px;">
                    If you have any questions about this payment, please contact us.
                </p>
            </div>
            
            <div class="footer">
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 30px;">
                    <tr>
                        <td style="padding: 20px 25px; background-color: #f8f9fa; border-top: 1px solid #e9ecef;">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td style="font-size: 13px; line-height: 1.8; color: #495057; font-family: Arial, sans-serif; padding-bottom: 15px;">
                                        <strong style="font-size: 14px;">Oceane Mootosamy</strong><br>
                                        Client Services Coordinator<br>
                                        Express & Freight<br>
                                        T: +230 4602828 | M: +230 52 58 32 84<br>
                                        <strong>Chronopost (Mauritius) Ltd.</strong><br>
                                        IBL Business Park, Cassis<br>
                                        Port Louis, Mauritius<br>
                                        BRN: C14126905
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 15px 0; border-top: 2px solid #495057;"></td>
                                </tr>
                                <tr>
                                    <td style="font-size: 11px; color: #6c757d; line-height: 1.6; padding-top: 10px;">
                                        All business being carried out with any party shall be conducted in accordance with our Standard Trading Conditions available on chronopost.mu. Any views expressed in this email are those of the sender only. The content of this email is confidential and intended solely for the use of the recipient(s). If received in error, it should be removed from the system without being read, copied, distributed or disclosed to anyone. Every care has been taken for this email to reach the recipient(s) free from computer viruses. No liability will be accepted for any loss or damage which may be caused. We process your personal data in accordance with the Data Protection Act 2017, which is itself aligned with the General Data Protection Regulation.
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return html


async def send_payment_email(
    recipient_email: str,
    payment_data: dict
) -> dict:
    """
    Send payment link email to customer
    
    Args:
        recipient_email: Customer's email address
        payment_data: Dictionary containing payment information
        
    Returns:
        dict: Status of email sending
    """
    
    try:
        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = f"Payment Request - Order {payment_data['order_number']}"
        message['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        message['To'] = recipient_email
        
        # Create HTML version
        html_content = create_payment_email_template(payment_data)
        html_part = MIMEText(html_content, 'html')
        message.attach(html_part)
        
        # Format amount for text version too
        formatted_amount_text = format_amount(payment_data['amount'])
        
        # Create plain text version as fallback
        text_content = f"""
Dear {payment_data['client_first_name']} {payment_data['client_last_name']},

You have received a payment request from Chronopost Mauritius Ltd.

Order Details:
- Order Name: {payment_data['order_name']}
- Order Number: {payment_data['order_number']}
- Reference: {payment_data['reference']}
- Amount: {payment_data['currency']} {formatted_amount_text}

To complete your payment, please visit:
{payment_data['payment_link']}

This is a secure payment link powered by VISA. Your payment information is encrypted and protected.

If you have any questions about this payment, please contact us.

Best regards,

Oceane Mootosamy
Client Services Coordinator
Express & Freight
T: +230 4602828 | M: +230 52 58 32 84
Chronopost (Mauritius) Ltd.
IBL Business Park, Cassis
Port Louis, Mauritius
BRN: C14126905
__________________________________________________

All business being carried out with any party shall be conducted in accordance with our Standard Trading Conditions available on chronopost.mu. Any views expressed in this email are those of the sender only. The content of this email is confidential and intended solely for the use of the recipient(s). If received in error, it should be removed from the system without being read, copied, distributed or disclosed to anyone. Every care has been taken for this email to reach the recipient(s) free from computer viruses. No liability will be accepted for any loss or damage which may be caused. We process your personal data in accordance with the Data Protection Act 2017, which is itself aligned with the General Data Protection Regulation.
        """
        text_part = MIMEText(text_content, 'plain')
        message.attach(text_part)
        
        # Send email
        if not SMTP_PASSWORD:
            logger.warning("SMTP_PASSWORD not configured. Email not sent.")
            return {
                "success": False,
                "error": "SMTP credentials not configured. Please set SMTP_PASSWORD in .env file."
            }
        
        async with aiosmtplib.SMTP(
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            use_tls=True,
            timeout=30
        ) as smtp:
            await smtp.login(SMTP_USER, SMTP_PASSWORD)
            await smtp.send_message(message)
        
        logger.info(f"Payment email sent successfully to {recipient_email}")
        return {
            "success": True,
            "message": f"Payment email sent successfully to {recipient_email}"
        }
        
    except aiosmtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed: {str(e)}")
        return {
            "success": False,
            "error": "SMTP authentication failed. Please check your email credentials."
        }
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to send email: {str(e)}"
        }
