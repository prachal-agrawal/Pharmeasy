import { paymentAPI, ordersAPI } from './api'
import toast from 'react-hot-toast'

/**
 * Complete Razorpay payment flow:
 * 1. Create Razorpay order on backend
 * 2. Open Razorpay checkout modal
 * 3. Verify signature on backend
 * 4. Place order in DB with payment_ref
 *
 * @param {Object} options
 * @param {number}   options.amount         - Total in INR
 * @param {Object}   options.orderPayload   - Body to send to POST /api/orders
 * @param {Object}   options.userInfo       - { name, email, phone }
 * @param {Function} options.onSuccess      - callback(order) after everything succeeds
 * @param {Function} options.onFailure      - callback(error) on failure
 */
export async function initiateRazorpayPayment({ amount, orderPayload, userInfo, onSuccess, onFailure }) {
  try {
    // Step 1 — Create Razorpay order via backend
    const { data: rzpData } = await paymentAPI.createOrder(amount)

    // Step 2 — Open Razorpay checkout modal
    const options = {
      key:         rzpData.key_id,
      amount:      rzpData.amount,       // in paise
      currency:    rzpData.currency,
      name:        'MathuraPharmeasy',
      description: 'Online Pharmacy Order',
      image:       '/logo.png',
      order_id:    rzpData.razorpay_order_id,

      prefill: {
        name:    userInfo?.name  || '',
        email:   userInfo?.email || '',
        contact: userInfo?.phone || '',
      },

      theme: { color: '#0F6E56' },

      // Called by Razorpay after successful payment
      handler: async (response) => {
        try {
          // Step 3 — Verify signature on backend
          const { data: verifyData } = await paymentAPI.verify({
            razorpay_order_id:   response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature:  response.razorpay_signature,
            internal_order_id:   0,   // placeholder; updated after order placed
          })

          if (!verifyData.verified) throw new Error('Payment verification failed')

          // Step 4 — Place order in DB with payment reference
          const { data: order } = await ordersAPI.place({
            ...orderPayload,
            payment_ref: response.razorpay_payment_id,
          })

          // Re-verify with actual order id
          await paymentAPI.verify({
            razorpay_order_id:   response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature:  response.razorpay_signature,
            internal_order_id:   order.order_id,
          })

          toast.success('Payment successful!')
          onSuccess && onSuccess(order)
        } catch (err) {
          toast.error(err?.response?.data?.detail || 'Payment verification failed')
          onFailure && onFailure(err)
        }
      },

      modal: {
        ondismiss: () => {
          toast('Payment cancelled', { icon: '⚠️' })
          onFailure && onFailure(new Error('User dismissed'))
        },
      },
    }

    if (!window.Razorpay) {
      throw new Error('Razorpay SDK not loaded. Check your internet connection.')
    }

    const rzp = new window.Razorpay(options)
    rzp.on('payment.failed', (response) => {
      toast.error(`Payment failed: ${response.error.description}`)
      onFailure && onFailure(response.error)
    })
    rzp.open()

  } catch (err) {
    const msg = err?.response?.data?.detail || err.message || 'Payment initiation failed'
    toast.error(msg)
    onFailure && onFailure(err)
  }
}
