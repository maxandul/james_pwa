"""Fixed household-cart proof: no arbitrary products or checkout instructions."""
PRODUCTS = (
    {'id': '14684120', 'name': 'bluu Universal Waschstreifen', 'package': '60 Waschgänge', 'quantity': 2},
    {'id': '14730798', 'name': 'Barilla Spaghetti n.5', 'package': '500 g', 'quantity': 1},
    {'id': '37264242', 'name': 'Cirio Pizza Sauce', 'package': '400 g', 'quantity': 1},
)

CART_PREPARATION = '''Complete all normal sign-in stages described above BEFORE checking the cart gate.
Never treat accepted field input or an intermediate login page as the end of login.
Proceed to cart changes only after a signed-in existing-account view is visibly
established. If the completed login still leaves account identity uncertain,
stop and report ACCOUNT_NOT_VERIFIED. If login itself fails, use its specific
failure report (LOGIN_REJECTED, VERIFICATION_REQUIRED, LOGIN_INCOMPLETE or
REDIRECT_PENDING) instead. Do not use a guest cart as proof.
You may inspect products and change ONLY the three explicitly consented test
cart lines. Never create accounts, change account settings, save payment data,
begin checkout, place an order, subscribe, or pay. Never contact anyone.
Read the current cart before changing anything. Preserve every unrelated line.
If quantities or contents change unexpectedly during the task, stop and report
CART_CONFLICT; another household member may be editing the shared cart.
The following are TOTAL TARGET quantities, never quantities to add blindly:
'''+ '\n'.join(f"- {p['name']}, {p['package']}, Galaxus product ID {p['id']}: target {p['quantity']} packs." for p in PRODUCTS) + '''
These are arbitrary POC products, not household preferences. No substitutions,
bundles or additional products. Stop if exact identity/variant, stock, price or
quantity cannot be established. Report PRODUCT_UNAVAILABLE for an unavailable
exact product. If an existing quantity exceeds a target, do not reduce it;
stop and report CART_CONFLICT. If the target already matches, leave it alone.
Only increase a lower quantity to its target. After an uncertain click, inspect
the cart before retrying. Never repeat Add blindly. Changes may remain partial
if the test stops; do not attempt an uncertain rollback or delete other items.
Finally reopen/refresh the cart and inspect each exact product ID and quantity.
Report CART_READY only after observing all three target lines (2/1/1) in the
signed-in cart. CART_READY is only your claim; the user will independently check
the same account's cart on their device. Never claim device visibility yourself.
Otherwise report CART_PARTIAL, CART_CONFLICT, PRODUCT_UNAVAILABLE,
ACCOUNT_NOT_VERIFIED or an applicable login failure. Do not output account data.
Finish with exactly one fixed line, no free text:
JAMES_LOGIN_REPORT=CART_READY
JAMES_LOGIN_REPORT=CART_PARTIAL
JAMES_LOGIN_REPORT=CART_CONFLICT
JAMES_LOGIN_REPORT=PRODUCT_UNAVAILABLE
JAMES_LOGIN_REPORT=ACCOUNT_NOT_VERIFIED
JAMES_LOGIN_REPORT=LOGIN_REJECTED
JAMES_LOGIN_REPORT=VERIFICATION_REQUIRED
JAMES_LOGIN_REPORT=LOGIN_INCOMPLETE
JAMES_LOGIN_REPORT=REDIRECT_PENDING
JAMES_LOGIN_REPORT=ACCESS_BLOCKED
JAMES_LOGIN_REPORT=AUTH_UNAVAILABLE
JAMES_LOGIN_REPORT=UNSUPPORTED_METHOD
JAMES_LOGIN_REPORT=UNKNOWN
The temporary browser will be deleted. No screenshots or private text are saved.
'''
