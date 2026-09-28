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
-- 3. 상품 이미지 등록 (picsum.photos 무료 이미지)
-- ==============================================================================
-- 3-1. 베이직 크롭 티셔츠 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://picsum.photos/seed/vibe-top-1/600/800',
    true,
    1
from public.products
where slug = 'basic-crop-tshirt';

insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://picsum.photos/seed/vibe-top-detail/600/800',
    false,
    2
from public.products
where slug = 'basic-crop-tshirt';

-- 3-2. 와이드 데님 팬츠 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://picsum.photos/seed/vibe-bottom-1/600/800',
    true,
    1
from public.products
where slug = 'wide-denim-pants';

-- 3-3. 오버핏 코튼 자켓 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://picsum.photos/seed/vibe-outer-1/600/800',
    true,
    1
from public.products
where slug = 'overfit-cotton-jacket';

-- 3-4. 플로럴 미디 원피스 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://picsum.photos/seed/vibe-dress-1/600/800',
    true,
    1
from public.products
where slug = 'floral-midi-dress';

-- 3-5. 오버핏 티셔츠 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://picsum.photos/seed/vibe-top-overfit/600/800',
    true,
    1
from public.products
where slug = 'overfit-tshirt';

-- 3-6. 베이지 코튼 팬츠 이미지
insert into public.product_images (product_id, image_url, is_primary, display_order)
select
    id,
    'https://picsum.photos/seed/vibe-bottom-beige/600/800',
    true,
    1
from public.products
where slug = 'beige-pants';

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
