/**
 * Home hero promo carousel — static copy (no CMS). Edit here to change banners.
 * ctaHash: element id on Home; CTAs use Link to /#<id> (avoids / same-route no-ops on home). ctaTo: path when ctaHash is null.
 */
export const PROMO_SLIDES = [
  {
    id: 'trust',
    title: 'Your trusted online pharmacy',
    subtitle: 'Genuine medicines, fast delivery, and care you can count on.',
    ctaLabel: 'Browse catalog',
    ctaTo: null,
    ctaHash: 'home-catalog',
    theme: 'brand',
  },
  {
    id: 'delivery',
    title: 'Check delivery to your pinCode',
    subtitle: 'See how soon your order can reach you—enter your PIN or use your location.',
    ctaLabel: 'Check delivery',
    ctaTo: null,
    ctaHash: 'home-delivery-check',
    theme: 'info',
  },
  {
    id: 'checkout',
    title: 'Secure checkout with Razorpay',
    subtitle: 'Minimum order ₹500 · Free delivery on ₹2000+ · Online payment only.',
    ctaLabel: 'View cart',
    ctaTo: '/cart',
    ctaHash: null,
    theme: 'amber',
  },
  {
    id: 'rx',
    title: 'Prescription medicines made simple',
    subtitle: 'Upload your Rx at checkout when required—our team verifies quickly.',
    ctaLabel: 'How it works',
    ctaTo: null,
    ctaHash: 'home-how-rx',
    theme: 'light',
  },
]
