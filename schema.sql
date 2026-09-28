-- ==============================================================================
-- VIBE-FASHION 쇼핑몰 데이터베이스 스키마 (Supabase PostgreSQL)
-- ==============================================================================

-- 1. 확장 기능 활성화 (UUID 생성용)
create extension if not exists "uuid-ossp";

-- ==============================================================================
-- 2. 기본 테이블 생성
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 2-1. 회원 프로필 (profiles) - Supabase auth.users와 연동
-- ------------------------------------------------------------------------------
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text,
    full_name text,
    avatar_url text,
    phone_number varchar(20),
    grade varchar(20) default 'BRONZE' not null check (grade in ('BRONZE', 'SILVER', 'GOLD', 'VIP')),
    total_spent numeric(12, 0) default 0 not null check (total_spent >= 0),
    role varchar(20) default 'customer' not null check (role in ('customer', 'admin')),
    created_at timestamptz default timezone('utc'::text, now()) not null,
    updated_at timestamptz default timezone('utc'::text, now()) not null
);

comment on table public.profiles is '고객 프로필 정보 (auth.users 연동)';
comment on column public.profiles.grade is '고객 등급 (BRONZE, SILVER, GOLD, VIP)';
comment on column public.profiles.total_spent is '누적 구매 확정 금액';

-- ------------------------------------------------------------------------------
-- 2-2. 카테고리 (categories)
-- ------------------------------------------------------------------------------
create table if not exists public.categories (
    id uuid primary key default gen_random_uuid(),
    name varchar(100) not null,
    slug varchar(100) unique not null,
    parent_id uuid references public.categories(id) on delete set null,
    display_order int default 0 not null,
    is_active boolean default true not null,
    created_at timestamptz default timezone('utc'::text, now()) not null
);

comment on table public.categories is '상품 카테고리 (계층형 지원)';

-- ------------------------------------------------------------------------------
-- 2-3. 상품 (products)
-- ------------------------------------------------------------------------------
create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    category_id uuid references public.categories(id) on delete set null,
    name varchar(255) not null,
    slug varchar(255) unique,
    description text,
    price numeric(12, 0) not null check (price >= 0),
    discount_rate numeric(5, 2) default 0.00 not null check (discount_rate between 0 and 100),
    is_active boolean default true not null,
    is_featured boolean default false not null,
    views_count int default 0 not null,
    created_at timestamptz default timezone('utc'::text, now()) not null,
    updated_at timestamptz default timezone('utc'::text, now()) not null
);

comment on table public.products is '상품 마스터';

-- ------------------------------------------------------------------------------
-- 2-4. 상품 옵션 및 재고 (product_options)
-- ------------------------------------------------------------------------------
create table if not exists public.product_options (
    id uuid primary key default gen_random_uuid(),
    product_id uuid not null references public.products(id) on delete cascade,
    color varchar(50),
    size varchar(50),
    additional_price numeric(12, 0) default 0 not null,
    stock_quantity int default 0 not null check (stock_quantity >= 0),
    sku varchar(100) unique,
    created_at timestamptz default timezone('utc'::text, now()) not null
);

comment on table public.product_options is '상품 색상/사이즈 옵션 및 실시간 재고';

-- ------------------------------------------------------------------------------
-- 2-5. 상품 이미지 (product_images)
-- ------------------------------------------------------------------------------
create table if not exists public.product_images (
    id uuid primary key default gen_random_uuid(),
    product_id uuid not null references public.products(id) on delete cascade,
    image_url text not null,
    is_primary boolean default false not null,
    display_order int default 0 not null,
    created_at timestamptz default timezone('utc'::text, now()) not null
);

comment on table public.product_images is '상품 이미지 (대표 이미지 및 서브 이미지)';

-- ------------------------------------------------------------------------------
-- 2-6. 장바구니 (carts)
-- ------------------------------------------------------------------------------
create table if not exists public.carts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(id) on delete cascade,
    product_option_id uuid not null references public.product_options(id) on delete cascade,
    quantity int default 1 not null check (quantity > 0),
    created_at timestamptz default timezone('utc'::text, now()) not null,
    updated_at timestamptz default timezone('utc'::text, now()) not null,
    constraint unique_user_option unique (user_id, product_option_id)
);

comment on table public.carts is '사용자 장바구니';

-- ------------------------------------------------------------------------------
-- 2-7. 주문 (orders)
-- ------------------------------------------------------------------------------
create table if not exists public.orders (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(id) on delete cascade,
    order_number varchar(64) unique not null,
    status varchar(30) default 'PENDING_PAYMENT' not null check (
        status in ('PENDING_PAYMENT', 'PAID', 'PREPARING', 'SHIPPING', 'DELIVERED', 'CANCELLED', 'REFUNDED')
    ),
    total_amount numeric(12, 0) not null check (total_amount >= 0),
    discount_amount numeric(12, 0) default 0 not null check (discount_amount >= 0),
    final_amount numeric(12, 0) not null check (final_amount >= 0),
    recipient_name varchar(100) not null,
    recipient_phone varchar(20) not null,
    shipping_address text not null,
    shipping_memo text,
    tracking_number varchar(100),
    paid_at timestamptz,
    created_at timestamptz default timezone('utc'::text, now()) not null,
    updated_at timestamptz default timezone('utc'::text, now()) not null
);

comment on table public.orders is '주문 내역';

-- ------------------------------------------------------------------------------
-- 2-8. 주문 상세 품목 (order_items)
-- ------------------------------------------------------------------------------
create table if not exists public.order_items (
    id uuid primary key default gen_random_uuid(),
    order_id uuid not null references public.orders(id) on delete cascade,
    product_id uuid references public.products(id) on delete set null,
    product_option_id uuid references public.product_options(id) on delete set null,
    product_name varchar(255) not null,
    option_name varchar(255),
    quantity int not null check (quantity > 0),
    unit_price numeric(12, 0) not null check (unit_price >= 0),
    subtotal numeric(12, 0) not null check (subtotal >= 0),
    created_at timestamptz default timezone('utc'::text, now()) not null
);

comment on table public.order_items is '주문별 상품 상세 항목';

-- ------------------------------------------------------------------------------
-- 2-9. 환불/반품 (refunds)
-- ------------------------------------------------------------------------------
create table if not exists public.refunds (
    id uuid primary key default gen_random_uuid(),
    order_id uuid not null references public.orders(id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    reason text not null,
    refund_amount numeric(12, 0) not null check (refund_amount >= 0),
    status varchar(30) default 'REQUESTED' not null check (
        status in ('REQUESTED', 'APPROVED', 'REJECTED', 'COMPLETED')
    ),
    admin_memo text,
    processed_at timestamptz,
    created_at timestamptz default timezone('utc'::text, now()) not null,
    updated_at timestamptz default timezone('utc'::text, now()) not null
);

comment on table public.refunds is '환불 및 반품 요청/처리 내역';

-- ------------------------------------------------------------------------------
-- 2-10. 알림 (notifications)
-- ------------------------------------------------------------------------------
create table if not exists public.notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(id) on delete cascade,
    title varchar(200) not null,
    content text not null,
    type varchar(50) default 'GENERAL' not null check (
        type in ('GENERAL', 'ORDER', 'DELIVERY', 'PROMOTION', 'SYSTEM')
    ),
    is_read boolean default false not null,
    read_at timestamptz,
    created_at timestamptz default timezone('utc'::text, now()) not null
);

comment on table public.notifications is '고객 개인 알림 내역';

-- ------------------------------------------------------------------------------
-- 2-11. 리뷰 (reviews)
-- ------------------------------------------------------------------------------
create table if not exists public.reviews (
    id uuid primary key default gen_random_uuid(),
    product_id uuid not null references public.products(id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    order_id uuid references public.orders(id) on delete set null,
    rating smallint not null check (rating between 1 and 5),
    content text not null,
    image_url text,
    created_at timestamptz default timezone('utc'::text, now()) not null,
    updated_at timestamptz default timezone('utc'::text, now()) not null
);

comment on table public.reviews is '상품 구매 리뷰';

-- ==============================================================================
-- 3. 성능 최적화를 위한 인덱스 설정
-- ==============================================================================
create index if not exists idx_products_category on public.products(category_id);
create index if not exists idx_product_options_product on public.product_options(product_id);
create index if not exists idx_product_images_product on public.product_images(product_id);
create index if not exists idx_carts_user on public.carts(user_id);
create index if not exists idx_orders_user on public.orders(user_id);
create index if not exists idx_order_items_order on public.order_items(order_id);
create index if not exists idx_refunds_order on public.refunds(order_id);
create index if not exists idx_notifications_user_unread on public.notifications(user_id, is_read);
create index if not exists idx_reviews_product on public.reviews(product_id);

-- ==============================================================================
-- 4. 소셜 로그인 및 회원가입 시 프로필 자동 생성 트리거 (handle_new_user)
-- ==============================================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_full_name text;
    v_avatar_url text;
begin
    -- OAuth 소셜 로그인(Kakao, Google, Naver, GitHub 등) 메타데이터 추출
    v_full_name := coalesce(
        new.raw_user_meta_data->>'full_name',
        new.raw_user_meta_data->>'name',
        new.raw_user_meta_data->>'user_name',
        split_part(new.email, '@', 1)
    );

    v_avatar_url := coalesce(
        new.raw_user_meta_data->>'avatar_url',
        new.raw_user_meta_data->>'picture',
        new.raw_user_meta_data->>'profile_image'
    );

    -- public.profiles 테이블에 사용자 레코드 삽입
    insert into public.profiles (
        id,
        email,
        full_name,
        avatar_url,
        grade,
        total_spent,
        role
    ) values (
        new.id,
        new.email,
        v_full_name,
        v_avatar_url,
        'BRONZE',
        0,
        'customer'
    )
    on conflict (id) do update
    set
        email = excluded.email,
        full_name = coalesce(public.profiles.full_name, excluded.full_name),
        avatar_url = coalesce(public.profiles.avatar_url, excluded.avatar_url),
        updated_at = timezone('utc'::text, now());

    return new;
exception
    when others then
        -- 오류 발생 시 로그 기록 후 auth 회원가입 흐름 방해 방지
        raise warning '신규 사용자 프로필 생성 중 오류 발생: %', sqlerrm;
        return new;
end;
$$;

-- auth.users 테이블 대상 트리거 등록
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row
    execute function public.handle_new_user();

-- ==============================================================================
-- 5. 고객 등급 자동 업데이트 함수 및 트리거 (update_customer_grade)
-- ==============================================================================
-- 등급 기준:
-- VIP:    누적 구매액 1,000,000원 이상
-- GOLD:   누적 구매액 500,000원 이상 1,000,000원 미만
-- SILVER: 누적 구매액 200,000원 이상 500,000원 미만
-- BRONZE: 누적 구매액 200,000원 미만
-- ==============================================================================

create or replace function public.update_customer_grade(target_user_id uuid)
returns public.profiles
language plpgsql
security definer
set search_path = public
as $$
declare
    v_total_paid numeric(12, 0) := 0;
    v_total_refunded numeric(12, 0) := 0;
    v_net_spent numeric(12, 0) := 0;
    v_new_grade varchar(20) := 'BRONZE';
    v_updated_profile public.profiles;
begin
    if target_user_id is null then
        raise exception '유효하지 않은 사용자 ID입니다.';
    end if;

    -- 1. 결제 완료 또는 배송/완료된 실 결제 금액 합산 (PAID, PREPARING, SHIPPING, DELIVERED)
    select coalesce(sum(final_amount), 0)
    into v_total_paid
    from public.orders
    where user_id = target_user_id
      and status in ('PAID', 'PREPARING', 'SHIPPING', 'DELIVERED');

    -- 2. 승인/완료된 환불 금액 차감
    select coalesce(sum(refund_amount), 0)
    into v_total_refunded
    from public.refunds
    where user_id = target_user_id
      and status in ('APPROVED', 'COMPLETED');

    -- 3. 순수 누적 구매액 계산 (음수 방지)
    v_net_spent := greatest(0, v_total_paid - v_total_refunded);

    -- 4. 누적 구매액에 따른 등급 판정
    if v_net_spent >= 1000000 then
        v_new_grade := 'VIP';
    elsif v_net_spent >= 500000 then
        v_new_grade := 'GOLD';
    elsif v_net_spent >= 200000 then
        v_new_grade := 'SILVER';
    else
        v_new_grade := 'BRONZE';
    end if;

    -- 5. 프로필 테이블 업데이트
    update public.profiles
    set
        total_spent = v_net_spent,
        grade = v_new_grade,
        updated_at = timezone('utc'::text, now())
    where id = target_user_id
    returning * into v_updated_profile;

    return v_updated_profile;
end;
$$;

-- 주문 및 환불 상태 변경 시 자동으로 등급을 재계산하는 트리거 함수
create or replace function public.trigger_auto_update_customer_grade()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_target_user_id uuid;
begin
    if tg_op = 'DELETE' then
        v_target_user_id := old.user_id;
    else
        v_target_user_id := new.user_id;
    end if;

    if v_target_user_id is not null then
        perform public.update_customer_grade(v_target_user_id);
    end if;

    return null;
end;
$$;

-- 주문 테이블 상태 변경 시 자동 실행 트리거
drop trigger if exists trigger_orders_grade_update on public.orders;
create trigger trigger_orders_grade_update
    after insert or update of status, final_amount or delete on public.orders
    for each row
    execute function public.trigger_auto_update_customer_grade();

-- 환불 테이블 변경 시 자동 실행 트리거
drop trigger if exists trigger_refunds_grade_update on public.refunds;
create trigger trigger_refunds_grade_update
    after insert or update of status, refund_amount or delete on public.refunds
    for each row
    execute function public.trigger_auto_update_customer_grade();

-- ==============================================================================
-- 6. 행 단위 보안 (Row Level Security, RLS) 활성화 및 기본 정책
-- ==============================================================================

-- 6-1. RLS 활성화
alter table public.profiles enable row level security;
alter table public.categories enable row level security;
alter table public.products enable row level security;
alter table public.product_options enable row level security;
alter table public.product_images enable row level security;
alter table public.carts enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.refunds enable row level security;
alter table public.notifications enable row level security;
alter table public.reviews enable row level security;

-- 6-2. 프로필 (profiles) 정책
create policy "공개 프로필 조회 허용" on public.profiles
    for select using (true);

create policy "본인 프로필만 수정 허용" on public.profiles
    for update using (auth.uid() = id);

-- 6-3. 상품 및 카테고리 (categories, products, options, images) 정책
create policy "카테고리 누구나 조회 가능" on public.categories
    for select using (is_active = true);

create policy "활성 상품 누구나 조회 가능" on public.products
    for select using (is_active = true);

create policy "상품 옵션 누구나 조회 가능" on public.product_options
    for select using (true);

create policy "상품 이미지 누구나 조회 가능" on public.product_images
    for select using (true);

-- 6-4. 장바구니 (carts) 정책
create policy "본인 장바구니만 조회" on public.carts
    for select using (auth.uid() = user_id);

create policy "본인 장바구니만 추가" on public.carts
    for insert with check (auth.uid() = user_id);

create policy "본인 장바구니만 수정" on public.carts
    for update using (auth.uid() = user_id);

create policy "본인 장바구니만 삭제" on public.carts
    for delete using (auth.uid() = user_id);

-- 6-5. 주문 및 주문 품목 (orders, order_items) 정책
create policy "본인 주문만 조회" on public.orders
    for select using (auth.uid() = user_id);

create policy "본인 주문만 생성" on public.orders
    for insert with check (auth.uid() = user_id);

create policy "본인 주문 항목만 조회" on public.order_items
    for select using (
        exists (
            select 1 from public.orders
            where orders.id = order_items.order_id
              and orders.user_id = auth.uid()
        )
    );

-- 6-6. 환불 (refunds) 정책
create policy "본인 환불 내역만 조회" on public.refunds
    for select using (auth.uid() = user_id);

create policy "본인 환불 요청만 생성" on public.refunds
    for insert with check (auth.uid() = user_id);

-- 6-7. 알림 (notifications) 정책
create policy "본인 알림만 조회" on public.notifications
    for select using (auth.uid() = user_id);

create policy "본인 알림 읽음 처리 수정" on public.notifications
    for update using (auth.uid() = user_id);

-- 6-8. 리뷰 (reviews) 정책
create policy "리뷰 누구나 조회 가능" on public.reviews
    for select using (true);

create policy "본인만 리뷰 작성 가능" on public.reviews
    for insert with check (auth.uid() = user_id);

create policy "본인만 리뷰 수정 가능" on public.reviews
    for update using (auth.uid() = user_id);

create policy "본인만 리뷰 삭제 가능" on public.reviews
    for delete using (auth.uid() = user_id);
