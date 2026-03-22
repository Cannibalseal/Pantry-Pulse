# Pantry Pulse - Feature Roadmap

## ✅ Completed Features
- [x] Web scraper for grocery prices (9 stores)
- [x] Price history chart (90-day inflation tracking)
- [x] Optimized performance (timeout reductions, URL reachability removal)
- [x] Product detail pages with latest prices
- [x] Responsive design (Bootstrap 5)
- [x] Background scraping tasks
- [x] Database persistence (SQLite)
- [x] Search & Filter (search bar, category filtering, sorting)

---

## 🚀 High Priority Features
Status: 1/4 Implemented

### ✅ 1. **Search & Filter** (COMPLETED)
- [x] Search bar on homepage
- [x] Filter products by category
- [x] Sort by: price, name, newest
- **Impact**: Huge UX improvement for 300+ items
- **Status**: Done ✓

### 2. **Shopping List** 
- [ ] Add products to shopping list
- [ ] Calculate total cost across stores
- [ ] View recommendations (cheapest combination)
- [ ] Export/share list
- **Impact**: Core monetization feature
- **Est. Time**: 4-5 hours

### 3. **Price Alerts**
- [ ] Set price threshold alerts
- [ ] Browser notifications when price drops
- [ ] Email notifications (optional)
- [ ] Alert history/management
- **Impact**: Drives user engagement
- **Est. Time**: 3-4 hours

### 4. **Mobile Responsiveness**
- [ ] Improve mobile UI for charts
- [ ] Touch-friendly buttons and navigation
- [ ] Mobile-first design pass
- [ ] Test on iOS/Android
- **Impact**: Essential for mobile traffic
- **Est. Time**: 2-3 hours

---

## 📊 Medium Priority Features
Status: Plan after high-priority

### 5. **Product Favorites/Wishlist**
- [ ] Save favorite products
- [ ] Separate favorites view
- [ ] Quick price checks
- [ ] Sync with shopping list
- **Est. Time**: 2-3 hours

### 6. **Admin Dashboard**
- [ ] View scraping statistics
- [ ] Monitor scraper errors
- [ ] Manual scrape triggers
- [ ] Store/product management
- [ ] Scrape interval configuration
- **Est. Time**: 4-5 hours

### 7. **Product Comparison**
- [ ] Compare 2-3 products side-by-side
- [ ] Side-by-side price chart
- [ ] Price difference highlighting
- [ ] Export comparison as PDF/CSV
- **Est. Time**: 3-4 hours

### 8. **Pagination/Lazy Loading**
- [ ] Paginate product list
- [ ] Infinite scroll option
- [ ] Improve homepage load speed
- [ ] Sort products efficiently
- **Est. Time**: 1-2 hours

---

## 💡 Lower Priority Features
Status: Consider later

### 9. **Dark Mode**
- [ ] Dark theme toggle
- [ ] User preference persistence
- **Est. Time**: 1-2 hours

### 10. **User Accounts**
- [ ] User authentication
- [ ] Save preferences
- [ ] Price alert history
- [ ] Shopping list sync across devices
- **Est. Time**: 6-8 hours

### 11. **Rate Limiting & Robustness**
- [ ] Implement rate limiting
- [ ] Better error handling for scraper failures
- [ ] Graceful degradation
- [ ] Retry logic with exponential backoff
- **Est. Time**: 2-3 hours

### 12. **Docker Support**
- [ ] Create Dockerfile
- [ ] docker-compose.yml for easy deployment
- [ ] Environment variable examples
- **Est. Time**: 1-2 hours

### 13. **Unit Tests**
- [ ] Test scraper logic
- [ ] Test Flask routes
- [ ] Test database operations
- [ ] CI/CD integration
- **Est. Time**: 4-5 hours

### 14. **Internationalization (i18n)**
- [ ] Multi-language support (EN, SK, CZ, etc.)
- [ ] Currency conversion
- [ ] Regional price comparisons
- **Est. Time**: 3-4 hours

---

## 🐛 Known Issues
- Scraper occasionally fails on network timeouts
- No user session management
- Chart needs more data points for accuracy
- Mobile layout could use refinement

## 📝 Notes
- All times are estimates
- Prioritize based on user feedback
- Test thoroughly after each feature
- Update README after major releases
