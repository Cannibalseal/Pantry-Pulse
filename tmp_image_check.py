from pantry_pulse.selenium_scraper import PRODUCTS
from pantry_pulse.app import get_product_image_url, get_product_category

category_images_values = {
    'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1551467847-0d94f8c0cd50?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1566385101042-1a0aa0c1268c?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1619566636858-adf2597f7335?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1567721913486-6585f069b332?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1544148103-0773bf10d330?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1582722872445-70da27a7a1a?w=400&h=400&fit=crop',
    'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=400&fit=crop',
}

fallback_url = 'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400&h=400&fit=crop'

missed = []
for p in PRODUCTS:
    url = get_product_image_url(p)
    if url == fallback_url or url in category_images_values:
        missed.append((p, get_product_category(p), url))

print('missed count:', len(missed))
for i, (p, cat, url) in enumerate(missed[:40], 1):
    print(i, repr(p), cat, url)
