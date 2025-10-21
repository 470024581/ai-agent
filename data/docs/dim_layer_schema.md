# DIM Layer (Dimension) Schema Design - Display-Time Resolution

## Overview
The DIM layer provides dimension tables for display-time resolution, containing descriptive attributes that are referenced by foreign keys in the DWD fact tables. This layer ensures data consistency and provides human-readable information for analytical queries and reporting.

## Design Philosophy

### Core Principles
- **Display-Time Resolution**: Resolve dimension names at query/display time
- **Data Consistency**: Maintain referential integrity without redundant data
- **Single Source of Truth**: Each dimension has one authoritative source
- **Slowly Changing Dimensions**: Handle dimension attribute changes over time
- **Permanent Storage**: Dimension data is permanently stored without retention periods

### Why Separate DIM Layer?

#### 1. **Data Consistency Strategy**
- **Foreign Key Only**: Store only foreign keys in fact tables, not dimension names
- **Display-Time Resolution**: Resolve dimension names at query/display time
- **Audit Trail**: Maintain complete data lineage and quality tracking
- **Change Management**: Handle dimension attribute changes without affecting fact data

#### 2. **Performance Optimization**
- **Reduced Storage**: Avoid redundant dimension data in fact tables
- **Faster Updates**: Update dimension attributes without touching fact data
- **Better Caching**: Dimension tables can be cached separately
- **Query Flexibility**: Support various dimension attribute combinations

#### 3. **Business Benefits**
- **Data Quality**: Ensure consistent dimension attributes across all queries
- **Maintenance**: Easier to maintain and update dimension data
- **Flexibility**: Support for various analytical patterns and reporting needs
- **Scalability**: Design scales with business growth and new requirements

---

## DIM Table Structure

### Customer Dimension

#### Table: dim_customer
**Purpose**: Customer dimension table for display-time resolution
**Source**: customers table
**Update Frequency**: Daily
**Design Rationale**: Single source of truth for customer descriptive attributes

##### Structure
| Column | Type | Constraints | Description | Source Mapping |
|--------|------|-------------|-------------|----------------|
| customer_id | TEXT | PRIMARY KEY | Customer identifier | customers.customer_id |
| customer_name | VARCHAR(200) | NOT NULL | Customer name | customers.customer_name |
| contact_person | VARCHAR(100) | NULL | Contact person | customers.contact_person |
| email | VARCHAR(100) | NULL | Email address | customers.email |
| phone | VARCHAR(20) | NULL | Phone number | customers.phone |
| address | TEXT | NULL | Address | customers.address |
| customer_type | VARCHAR(20) | NOT NULL | Customer type | customers.customer_type |
| region | VARCHAR(50) | NULL | Geographic region | Derived from address |
| created_at | DATETIME | NOT NULL | Creation timestamp | customers.created_at |
| updated_at | DATETIME | NOT NULL | Update timestamp | customers.updated_at |
| days_since_update | INTEGER | NULL | Days since update | DATEDIFF(DAY, updated_at, GETDATE()) |
| is_active_customer | BOOLEAN | NOT NULL | Active customer flag | Derived |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

##### Business Rules
- Customer types: Individual, Corporate, VIP
- Regions: North, South, East, West, Central (derived from address)
- Active customer: Updated within last 90 days
- Email format validation: Must contain @ symbol
- Phone format validation: Must be numeric with country code

##### Derived Attributes
- **region**: Extracted from address field using geographic mapping
- **is_active_customer**: Based on days_since_update <= 90
- **days_since_update**: Calculated from updated_at timestamp

##### Analytics Capabilities
- **Customer Segmentation**: Group customers by type, region, and activity
- **Geographic Analysis**: Analyze customer distribution by region
- **Contact Management**: Track customer contact information and updates
- **Activity Monitoring**: Monitor customer data freshness and activity

---

### Product Dimension

#### Table: dim_product
**Purpose**: Product dimension table for display-time resolution
**Source**: products table
**Update Frequency**: Daily
**Design Rationale**: Single source of truth for product descriptive attributes

##### Structure
| Column | Type | Constraints | Description | Source Mapping |
|--------|------|-------------|-------------|----------------|
| product_id | TEXT | PRIMARY KEY | Product identifier | products.product_id |
| product_name | VARCHAR(200) | NOT NULL | Product name | products.product_name |
| category | VARCHAR(100) | NOT NULL | Product category | products.category |
| unit_price | DECIMAL(12,2) | NOT NULL | Unit price | products.unit_price |
| price_range | VARCHAR(20) | NOT NULL | Price range | Derived from unit_price |
| created_at | DATETIME | NOT NULL | Creation timestamp | Generated |
| updated_at | DATETIME | NOT NULL | Update timestamp | Generated |
| days_since_update | INTEGER | NULL | Days since update | DATEDIFF(DAY, updated_at, GETDATE()) |
| is_active_product | BOOLEAN | NOT NULL | Active product flag | Derived |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

##### Business Rules
- Price ranges: Low (<50), Medium (50-200), High (200-1000), Premium (>1000)
- Active product: Has sales within last 90 days
- Unit price validation: Must be > 0
- Product name validation: Cannot be empty or null
- Category validation: Must be from predefined list

##### Derived Attributes
- **price_range**: Categorized based on unit_price value
- **is_active_product**: Based on recent sales activity
- **days_since_update**: Calculated from updated_at timestamp

##### Analytics Capabilities
- **Product Categorization**: Group products by category and price range
- **Price Analysis**: Analyze product pricing strategies
- **Product Lifecycle**: Track product activity and updates
- **Catalog Management**: Manage product catalog and attributes

---

## Data Integration Strategy

### ETL Processing Logic

#### Customer Dimension ETL
```python
def process_customer_dimension():
    # Extract customer data
    customer_data = extract_customer_data()
    
    # Transform and enrich
    for customer in customer_data:
        # Derive region from address
        region = extract_region_from_address(customer.address)
        
        # Calculate derived attributes
        days_since_update = (datetime.now() - customer.updated_at).days
        is_active_customer = days_since_update <= 90
        
        customer_record = {
            'customer_id': customer.customer_id,
            'customer_name': customer.customer_name,
            'contact_person': customer.contact_person,
            'email': customer.email,
            'phone': customer.phone,
            'address': customer.address,
            'customer_type': customer.customer_type,
            'region': region,
            'created_at': customer.created_at,
            'updated_at': customer.updated_at,
            'days_since_update': days_since_update,
            'is_active_customer': is_active_customer,
            'etl_batch_id': get_current_batch_id(),
            'etl_timestamp': datetime.now()
        }
        
        # Validate business rules
        if validate_customer_record(customer_record):
            # Load to DIM
            load_customer_dimension(customer_record)
        else:
            # Log validation errors
            log_validation_error(customer_record)

def extract_region_from_address(address):
    """Extract region from address using geographic mapping"""
    if not address:
        return 'Unknown'
    
    address_lower = address.lower()
    
    # Simple region mapping (can be enhanced with geocoding)
    if any(keyword in address_lower for keyword in ['north', 'northern']):
        return 'North'
    elif any(keyword in address_lower for keyword in ['south', 'southern']):
        return 'South'
    elif any(keyword in address_lower for keyword in ['east', 'eastern']):
        return 'East'
    elif any(keyword in address_lower for keyword in ['west', 'western']):
        return 'West'
    elif any(keyword in address_lower for keyword in ['central', 'center']):
        return 'Central'
    else:
        return 'Unknown'

def validate_customer_record(customer_record):
    """Validate customer record against business rules"""
    # Email validation
    if customer_record['email'] and '@' not in customer_record['email']:
        return False
    
    # Phone validation (basic)
    if customer_record['phone'] and not customer_record['phone'].replace('+', '').replace('-', '').replace(' ', '').isdigit():
        return False
    
    # Required fields validation
    if not customer_record['customer_name'] or not customer_record['customer_type']:
        return False
    
    return True
```

#### Product Dimension ETL
```python
def process_product_dimension():
    # Extract product data
    product_data = extract_product_data()
    
    # Get sales data for activity calculation
    sales_data = extract_sales_data()
    
    # Calculate product activity
    product_activity = {}
    for sale in sales_data:
        product_id = sale.product_id
        if product_id not in product_activity:
            product_activity[product_id] = []
        product_activity[product_id].append(sale.sale_date)
    
    # Transform and enrich
    for product in product_data:
        # Derive price range
        price_range = get_price_range(product.unit_price)
        
        # Calculate activity status
        last_sale_date = max(product_activity.get(product.product_id, [datetime.min]))
        days_since_last_sale = (datetime.now() - last_sale_date).days
        is_active_product = days_since_last_sale <= 90
        
        product_record = {
            'product_id': product.product_id,
            'product_name': product.product_name,
            'category': product.category,
            'unit_price': product.unit_price,
            'price_range': price_range,
            'created_at': datetime.now(),  # Assuming products don't have creation date
            'updated_at': datetime.now(),  # Assuming products don't have update date
            'days_since_update': 0,  # Will be calculated based on sales activity
            'is_active_product': is_active_product,
            'etl_batch_id': get_current_batch_id(),
            'etl_timestamp': datetime.now()
        }
        
        # Validate business rules
        if validate_product_record(product_record):
            # Load to DIM
            load_product_dimension(product_record)
        else:
            # Log validation errors
            log_validation_error(product_record)

def get_price_range(unit_price):
    """Categorize price into ranges"""
    if unit_price < 50:
        return 'Low'
    elif unit_price < 200:
        return 'Medium'
    elif unit_price < 1000:
        return 'High'
    else:
        return 'Premium'

def validate_product_record(product_record):
    """Validate product record against business rules"""
    # Price validation
    if product_record['unit_price'] <= 0:
        return False
    
    # Required fields validation
    if not product_record['product_name'] or not product_record['category']:
        return False
    
    # Category validation (can be enhanced with predefined list)
    valid_categories = ['Electronics', 'Clothing', 'Books', 'Home', 'Sports', 'Beauty', 'Food']
    if product_record['category'] not in valid_categories:
        return False
    
    return True
```

---

## Query Performance Examples

### Customer Analysis Query
```sql
-- Customer analysis with dimension resolution
SELECT 
    c.customer_name,
    c.customer_type,
    c.region,
    c.is_active_customer,
    s.total_spent,
    s.transaction_count,
    s.avg_transaction_value
FROM (
    SELECT 
        customer_id,
        SUM(total_amount) as total_spent,
        COUNT(*) as transaction_count,
        AVG(total_amount) as avg_transaction_value
    FROM dwd_sales_detail
    WHERE sale_date >= '2024-01-01'
    GROUP BY customer_id
) s
LEFT JOIN dim_customer c ON s.customer_id = c.customer_id
ORDER BY s.total_spent DESC;

-- Customer segmentation by region
SELECT 
    c.region,
    c.customer_type,
    COUNT(*) as customer_count,
    SUM(s.total_spent) as total_revenue,
    AVG(s.avg_transaction_value) as avg_transaction_value
FROM (
    SELECT 
        customer_id,
        SUM(total_amount) as total_spent,
        AVG(total_amount) as avg_transaction_value
    FROM dwd_sales_detail
    WHERE sale_date >= '2024-01-01'
    GROUP BY customer_id
) s
LEFT JOIN dim_customer c ON s.customer_id = c.customer_id
GROUP BY c.region, c.customer_type
ORDER BY total_revenue DESC;
```

### Product Analysis Query
```sql
-- Product analysis with dimension resolution
SELECT 
    p.product_name,
    p.category,
    p.price_range,
    p.is_active_product,
    s.total_revenue,
    s.total_quantity,
    s.avg_sale_price
FROM (
    SELECT 
        product_id,
        SUM(total_amount) as total_revenue,
        SUM(quantity_sold) as total_quantity,
        AVG(price_per_unit) as avg_sale_price
    FROM dwd_sales_detail
    WHERE sale_date >= '2024-01-01'
    GROUP BY product_id
) s
LEFT JOIN dim_product p ON s.product_id = p.product_id
ORDER BY s.total_revenue DESC;

-- Category performance analysis
SELECT 
    p.category,
    p.price_range,
    COUNT(*) as product_count,
    SUM(s.total_revenue) as category_revenue,
    AVG(s.avg_sale_price) as avg_category_price
FROM (
    SELECT 
        product_id,
        SUM(total_amount) as total_revenue,
        AVG(price_per_unit) as avg_sale_price
    FROM dwd_sales_detail
    WHERE sale_date >= '2024-01-01'
    GROUP BY product_id
) s
LEFT JOIN dim_product p ON s.product_id = p.product_id
GROUP BY p.category, p.price_range
ORDER BY category_revenue DESC;
```

---

## Benefits of This DIM Design

### 1. **Data Consistency Benefits**
- **Single Source of Truth**: Each dimension has one authoritative source
- **Referential Integrity**: Maintains data consistency across all queries
- **Change Management**: Handle dimension attribute changes without affecting fact data
- **Audit Trail**: Complete data lineage and quality tracking

### 2. **Performance Benefits**
- **Reduced Storage**: Avoid redundant dimension data in fact tables
- **Faster Updates**: Update dimension attributes without touching fact data
- **Better Caching**: Dimension tables can be cached separately
- **Query Optimization**: Optimized for display-time resolution

### 3. **Business Benefits**
- **Data Quality**: Ensure consistent dimension attributes across all queries
- **Maintenance**: Easier to maintain and update dimension data
- **Flexibility**: Support for various analytical patterns and reporting needs
- **Scalability**: Design scales with business growth and new requirements

### 4. **Operational Benefits**
- **Simplified ETL**: Clear separation of concerns between fact and dimension data
- **Easier Debugging**: Clear data lineage and audit trails
- **Flexible Analytics**: Support for various analytical patterns
- **Future-Proof**: Design accommodates new analytical requirements

This optimized DIM design provides a solid foundation for maintaining data consistency and supporting comprehensive business intelligence needs while ensuring optimal performance for analytical queries.
