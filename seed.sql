-- ==============================================================================
-- VIBE-FASHION 쇼핑몰 초기 데이터(Seed) SQL
-- ==============================================================================

-- 1. 카테고리 7개 등록
insert into public.categories (name, slug, display_order, is_active)
values
    ('상의', 'top', 1, true),
    ('하의', 'bottom', 2, true),
    ('아우터', 'outer', 3, true),
    ('원피스/세트', 'dress', 4, true),
    ('액세서리', 'acc', 5, true),
    ('가방', 'bag', 6, true),
    ('신발', 'shoes', 7, true)
on conflict (slug) do update
set
    name = excluded.name,
    display_order = excluded.display_order,
    is_active = excluded.is_active;

-- ==============================================================================
-- 2. 샘플 상품 6개 등록
-- (베이직 크롭 티셔츠의 경우 정가 29,900원에 할인율 약 33.44% 적용되어 판매가 19,900원 구성)
-- ==============================================================================
insert into public.products (category_id, name, slug, description, price, discount_rate, is_active, is_featured)
values
    (
        (select id from public.categories where slug = 'top'),
        '베이직 크롭 티셔츠',
        'basic-crop-tshirt',
        '데일리로 편안하게 착용하기 좋은 코튼 베이직 크롭 반팔 티셔츠입니다.',
        29900,
        33.44,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'bottom'),
        '와이드 데님 팬츠',
        'wide-denim-pants',
        '자연스러운 워싱과 트렌디한 와이드 핏이 돋보이는 사계절 데님 팬츠입니다.',
        39900,
        0.00,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'outer'),
        '오버핏 코튼 자켓',
        'overfit-cotton-jacket',
        '탄탄한 코튼 소재로 제작되어 간절기에 가볍게 걸치기 좋은 오버핏 자켓입니다.',
        59900,
        0.00,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'dress'),
        '플로럴 미디 원피스',
        'floral-midi-dress',
        '화사한 플라워 패턴과 살랑이는 실루엣이 매력적인 페미닌 미디 원피스입니다.',
        45900,
        0.00,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'top'),
        '오버핏 티셔츠',
        'overfit-tshirt',
        '여유로운 루즈핏 실루엣으로 편안하고 스타일리시하게 착용 가능한 코튼 오버핏 티셔츠입니다.',
        32000,
        0.00,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'bottom'),
        '베이지 코튼 팬츠',
        'beige-pants',
        '내추럴한 베이지 톤과 여유로운 스트레이트 핏이 돋보이는 데일리 코튼 팬츠입니다.',
        42000,
        0.00,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'outer'),
        '블랙 바람막이',
        'black-windbreaker',
        '가볍고 방풍 기능이 뛰어난 트렌디한 스트릿 감성의 블랙 바람막이 자켓입니다.',
        69000,
        0.00,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'outer'),
        '화이트 블레이저',
        'white-blazer',
        '단정하고 세련된 테일러드 핏으로 모던한 무드를 완성하는 프리미엄 화이트 블레이저입니다.',
        89000,
        0.00,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'top'),
        '옐로우가디건',
        'yellow-cardigan',
        '화사한 파스텔 옐로우 컬러와 부드러운 니트 텍스처가 돋보이는 루즈핏 브이넥 가디건입니다.',
        45000,
        0.00,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'acc'),
        '휴대용파우치',
        'portable-pouch',
        '넉넉한 수납공간과 미니멀한 질감으로 화장품 및 소지품을 간편하게 휴대할 수 있는 멀티 파우치입니다.',
        15000,
        0.00,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'bag'),
        '휴대용에코백',
        'portable-eco-bag',
        '튼튼한 코튼 캔버스 소재로 가볍고 접어서 휴대하기 좋은 내추럴 무드의 데일리 에코백입니다.',
        19000,
        0.00,
        true,
        true
    ),
    (
        (select id from public.categories where slug = 'acc'),
        '퍼플스타킹',
        'purple-stockings',
        '감각적인 컬러감과 쫀쫀한 텐션감으로 다리 라인을 슬림하고 트렌디하게 연출해주는 퍼플 타이즈입니다.',
        12000,
        0.00,
        true,
        true
    )
on conflict (slug) do update
set
    category_id = excluded.category_id,
    name = excluded.name,
    description = excluded.description,
    price = excluded.price,
    discount_rate = excluded.discount_rate,
    is_active = excluded.is_active,
    is_featured = excluded.is_featured;

-- ==============================================================================
-- 3. 상품 이미지 등록 (Unsplash 고화질 의류 이미지)
-- ==============================================================================
-- 3-1. 베이직 크롭 티셔츠 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'basic-crop-tshirt';

insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1534126511673-b6899657816a?auto=format&fit=crop&w=800&q=80',
    false,
    2
from public.products
where slug = 'basic-crop-tshirt';

-- 3-2. 와이드 데님 팬츠 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1582418702059-97ebafb35d09?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'wide-denim-pants';

-- 3-3. 오버핏 코튼 자켓 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'overfit-cotton-jacket';

-- 3-4. 플로럴 미디 원피스 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'floral-midi-dress';

-- 3-5. 오버핏 티셔츠 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'overfit-tshirt';

-- 3-6. 베이지 코튼 팬츠 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1473966968600-fa801b869a1a?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'beige-pants';

-- 3-7. 블랙 바람막이 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1544441893-675973e31985?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'black-windbreaker';

-- 3-8. 화이트 블레이저 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'white-blazer';

-- 3-9. 옐로우가디건 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'yellow-cardigan';

-- 3-10. 휴대용파우치 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'portable-pouch';

-- 3-11. 휴대용에코백 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1544816155-12df9643f363?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'portable-eco-bag';

-- 3-12. 퍼플스타킹 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://images.unsplash.com/photo-1588850561407-ed78c282e89b?auto=format&fit=crop&w=800&q=80',
    true,
    1
from public.products
where slug = 'purple-stockings';

-- ==============================================================================
-- 4. 첫 번째 상품(베이직 크롭 티셔츠) 옵션 9개 등록
-- (블랙 / 화이트 / 베이지 × S / M / L)
-- ==============================================================================
insert into public.product_options (product_id, color, size, additional_price, stock_quantity, sku)
select
    p.id,
    opt.color,
    opt.size,
    0 as additional_price,
    50 as stock_quantity,
    'BCT-' || upper(substr(opt.color_code, 1, 3)) || '-' || opt.size as sku
from public.products p
cross join (
    values
        ('블랙', 'BLK', 'S'),
        ('블랙', 'BLK', 'M'),
        ('블랙', 'BLK', 'L'),
        ('화이트', 'WHT', 'S'),
        ('화이트', 'WHT', 'M'),
        ('화이트', 'WHT', 'L'),
        ('베이지', 'BEG', 'S'),
        ('베이지', 'BEG', 'M'),
        ('베이지', 'BEG', 'L')
) as opt(color, color_code, size)
where p.slug = 'basic-crop-tshirt'
on conflict (sku) do update
set
    color = excluded.color,
    size = excluded.size,
    stock_quantity = excluded.stock_quantity;

-- 나머지 3개 상품 기본 옵션 등록 (선택적 주문 테스트용)
insert into public.product_options (product_id, color, size, additional_price, stock_quantity, sku)
select id, '중청', 'M', 0, 30, 'WDP-M' from public.products where slug = 'wide-denim-pants'
on conflict (sku) do nothing;

insert into public.product_options (product_id, color, size, additional_price, stock_quantity, sku)
select id, '베이지', 'FREE', 0, 20, 'OCJ-FREE' from public.products where slug = 'overfit-cotton-jacket'
on conflict (sku) do nothing;

insert into public.product_options (product_id, color, size, additional_price, stock_quantity, sku)
select id, '아이보리', 'FREE', 0, 25, 'FMD-FREE' from public.products where slug = 'floral-midi-dress'
on conflict (sku) do nothing;

insert into public.product_options (product_id, color, size, additional_price, stock_quantity, sku)
select id, '화이트', 'FREE', 0, 50, 'OTS-WHT-FREE' from public.products where slug = 'overfit-tshirt'
on conflict (sku) do nothing;

insert into public.product_options (product_id, color, size, additional_price, stock_quantity, sku)
select id, '베이지', 'M', 0, 40, 'BEG-PNT-M' from public.products where slug = 'beige-pants'
on conflict (sku) do nothing;
