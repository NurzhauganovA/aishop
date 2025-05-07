from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('product/<str:slug>/', views.product_detail, name='product_detail'),
    path('product/id/<int:product_id>/', views.product_detail_by_id, name='product_detail_by_id'),
    path('cart/', views.cart, name='cart'),
    path('add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('update-cart/', views.update_cart, name='update_cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('add-to-wishlist/', views.add_to_wishlist, name='add_to_wishlist'),
    path('leave-view-time/<int:product_id>/', views.leave_view_time, name='leave_view_time'),
    path('submit-review/<int:product_id>/', views.submit_review, name='submit_review'),
    path('track-product/<int:product_id>/', views.track_product, name='track_product'),
    
    # Seller dashboard
    path('seller/', views.SellerDashboardView.as_view(), name='seller_dashboard'),
    path('seller/products/', views.SellerProductsView.as_view(), name='seller_products'),
    path('seller/product/add/', views.SellerProductCreateView.as_view(), name='seller_product_add'),
    path('seller/product/<int:pk>/edit/', views.SellerProductUpdateView.as_view(), name='seller_product_edit'),
    path('seller/product/<int:pk>/delete/', views.SellerProductDeleteView.as_view(), name='seller_product_delete'),
    path('seller/orders/', views.SellerOrdersView.as_view(), name='seller_orders'),
    path('seller/order/<int:pk>/', views.SellerOrderDetailView.as_view(), name='seller_order_detail'),
    path('seller/order/<int:pk>/update-status/', views.SellerOrderUpdateStatusView.as_view(), name='seller_order_update_status'),
    path('seller/generate-description/', views.seller_generate_description, name='seller_generate_description'),
]