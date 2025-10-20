# Business Data Schema for AI Analytics Platform

## Overview
This document contains comprehensive metadata for business data tables designed for AI-powered analytics combining SQL-Agent capabilities with RAG (Retrieval-Augmented Generation) for intelligent data analysis and insights.

## Database Schema

### Table: customers
**Purpose**: Customer relationship management and analytics
**Domain**: Customer Data, CRM, Analytics

#### Structure
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| customer_id | TEXT | PRIMARY KEY | Unique customer identifier |
| customer_name | TEXT | NOT NULL | Customer name |
| contact_person | TEXT | NULL | Contact person name |
| phone | TEXT | NULL | Phone number |
| email | TEXT | NULL | Customer email address |
| address | TEXT | NULL | Full address |
| customer_type | TEXT | NOT NULL, DEFAULT 'regular' | Customer type (regular/vip/corporate) |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Record creation timestamp |
| updated_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Record update timestamp |

#### Relationships
- One-to-Many with orders: customer_id → orders.customer_id
- One-to-Many with sales: customer_id → sales.customer_id

#### Business Rules
- Each customer must have a unique customer_id
- Customer name is required for all customers
- Customer type determines service levels and pricing
- Contact information should be validated for accuracy

#### Analytics Use Cases
- Customer segmentation by type and location
- Customer contact analysis and communication patterns
- Customer registration trends and growth analysis
- Geographic analysis of customer distribution
- Customer type performance analysis

#### Sample Queries
```sql
-- Customer analysis by type
SELECT customer_type, COUNT(*) as customer_count, 
       COUNT(CASE WHEN email IS NOT NULL THEN 1 END) as customers_with_email,
       COUNT(CASE WHEN phone IS NOT NULL THEN 1 END) as customers_with_phone
FROM customers 
GROUP BY customer_type;

-- Customer registration trends
SELECT DATE(created_at) as reg_date, COUNT(*) as new_customers
FROM customers 
WHERE created_at >= '2024-01-01'
GROUP BY DATE(created_at)
ORDER BY reg_date;
```

---

### Table: products
**Purpose**: Product catalog management and analytics
**Domain**: Product Data, Catalog Management, Pricing

#### Structure
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| product_id | TEXT | PRIMARY KEY | Unique product identifier |
| product_name | TEXT | NOT NULL | Product name/title |
| category | TEXT | NOT NULL | Product category |
| unit_price | REAL | NOT NULL | Unit price |

#### Relationships
- One-to-Many with inventory: product_id → inventory.product_id
- One-to-Many with sales: product_id → sales.product_id

#### Business Rules
- Product ID must be unique across all products
- Product name and category are required
- Unit price must be positive
- Category should be standardized for consistency

#### Analytics Use Cases
- Product performance analysis by category
- Price analysis and optimization strategies
- Category performance comparison
- Product popularity analysis
- Revenue analysis by product

#### Sample Queries
```sql
-- Product analysis by category
SELECT category, COUNT(*) as product_count, 
       AVG(unit_price) as avg_price,
       MIN(unit_price) as min_price,
       MAX(unit_price) as max_price
FROM products 
GROUP BY category
ORDER BY avg_price DESC;

-- Product price distribution
SELECT category, 
       CASE 
         WHEN unit_price < 50 THEN 'Low'
         WHEN unit_price < 200 THEN 'Medium'
         ELSE 'High'
       END as price_range,
       COUNT(*) as product_count
FROM products
GROUP BY category, price_range
ORDER BY category, price_range;
```

---

### Table: inventory
**Purpose**: Stock level management and warehouse operations
**Domain**: Inventory Management, Warehouse Operations, Supply Chain

#### Structure
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| product_id | TEXT | PRIMARY KEY | Reference to products table |
| stock_level | INTEGER | NOT NULL | Current quantity in stock |
| last_updated | DATETIME | NOT NULL | Last update timestamp |

#### Relationships
- One-to-One with products: product_id → products.product_id

#### Business Rules
- Stock level must be non-negative
- Each product can have only one inventory record
- Last updated timestamp must be current
- Stock level should be updated when sales occur

#### Analytics Use Cases
- Stock level analysis and monitoring
- Low stock alerts and reorder recommendations
- Inventory turnover analysis
- Stock value analysis
- Inventory aging analysis

#### Sample Queries
```sql
-- Low stock analysis
SELECT p.product_name, p.category, i.stock_level, p.unit_price,
       (i.stock_level * p.unit_price) as stock_value
FROM inventory i
JOIN products p ON i.product_id = p.product_id
WHERE i.stock_level < 10
ORDER BY stock_value DESC;

-- Inventory turnover analysis
SELECT p.category, 
       AVG(i.stock_level) as avg_stock_level,
       COUNT(*) as product_count,
       SUM(i.stock_level * p.unit_price) as total_stock_value
FROM inventory i
JOIN products p ON i.product_id = p.product_id
GROUP BY p.category
ORDER BY total_stock_value DESC;
```

---

### Table: orders
**Purpose**: Order processing and fulfillment management
**Domain**: Order Management, Fulfillment, Customer Service

#### Structure
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| order_id | TEXT | PRIMARY KEY | Unique order identifier |
| customer_id | TEXT | NOT NULL | Reference to customer table |
| order_date | DATETIME | NOT NULL | Order placement date and time |
| total_amount | REAL | NOT NULL | Final order total |
| status | TEXT | NOT NULL, DEFAULT 'pending' | Order status (pending/confirmed/shipped/delivered/cancelled) |
| payment_method | TEXT | NULL | Payment method used |
| shipping_address | TEXT | NULL | Delivery address |
| notes | TEXT | NULL | Special instructions |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Record creation timestamp |
| updated_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Record update timestamp |

#### Relationships
- Many-to-One with customers: customer_id → customers.customer_id

#### Business Rules
- Order ID must be unique
- Customer ID must reference existing customer
- Total amount must be positive
- Order status should follow logical progression
- Order date cannot be in the future

#### Analytics Use Cases
- Order volume analysis and trend tracking
- Customer ordering behavior analysis
- Revenue analysis by period and customer
- Order status analysis and fulfillment performance
- Payment method analysis
- Geographic analysis of orders

#### Sample Queries
```sql
-- Order analysis by status
SELECT status, COUNT(*) as order_count, 
       AVG(total_amount) as avg_order_value,
       SUM(total_amount) as total_revenue
FROM orders 
GROUP BY status
ORDER BY order_count DESC;

-- Customer order analysis
SELECT c.customer_name, c.customer_type,
       COUNT(o.order_id) as order_count,
       SUM(o.total_amount) as total_spent,
       AVG(o.total_amount) as avg_order_value
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name, c.customer_type
ORDER BY total_spent DESC;
```

---

### Table: sales
**Purpose**: Sales transaction recording and analytics
**Domain**: Sales Analytics, Revenue Analysis, Performance Tracking

#### Structure
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| sale_id | TEXT | PRIMARY KEY | Unique sale identifier |
| product_id | TEXT | NOT NULL | Reference to products table |
| product_name | TEXT | NOT NULL | Product name at time of sale |
| quantity_sold | INTEGER | NOT NULL | Quantity sold |
| price_per_unit | REAL | NOT NULL | Price per unit at time of sale |
| total_amount | REAL | NOT NULL | Total amount for the sale |
| sale_date | DATETIME | NOT NULL | Sale date and time |

#### Relationships
- Many-to-One with products: product_id → products.product_id

#### Business Rules
- Sale ID must be unique
- Product ID must reference existing product
- Quantity sold must be positive
- Price per unit must be positive
- Total amount = quantity_sold * price_per_unit
- Sale date cannot be in the future

#### Analytics Use Cases
- Sales performance tracking and trend analysis
- Product performance identification
- Revenue analysis by period and product
- Sales volume analysis
- Price analysis and optimization
- Seasonal pattern identification

#### Sample Queries
```sql
-- Sales performance by product
SELECT s.product_name, p.category,
       COUNT(s.sale_id) as sales_count,
       SUM(s.quantity_sold) as total_quantity,
       SUM(s.total_amount) as total_revenue,
       AVG(s.price_per_unit) as avg_price
FROM sales s
JOIN products p ON s.product_id = p.product_id
GROUP BY s.product_id, s.product_name, p.category
ORDER BY total_revenue DESC;

-- Sales trend analysis
SELECT DATE(sale_date) as sale_date, 
       COUNT(*) as sales_count,
       SUM(total_amount) as daily_revenue,
       AVG(total_amount) as avg_sale_value
FROM sales
WHERE sale_date >= '2024-01-01'
GROUP BY DATE(sale_date)
ORDER BY sale_date;
```

---

## Cross-Table Analytics Patterns

### Customer Order Analysis
```sql
SELECT c.customer_name, c.customer_type,
       COUNT(DISTINCT o.order_id) as total_orders,
       SUM(o.total_amount) as total_spent,
       AVG(o.total_amount) as avg_order_value,
       MAX(o.order_date) as last_order_date
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name, c.customer_type
ORDER BY total_spent DESC;
```

### Product Performance Analysis
```sql
SELECT p.product_name, p.category,
       COUNT(s.sale_id) as sales_count,
       SUM(s.quantity_sold) as total_quantity,
       SUM(s.total_amount) as total_revenue,
       AVG(s.price_per_unit) as avg_sale_price,
       AVG(i.stock_level) as avg_stock_level
FROM products p
JOIN sales s ON p.product_id = s.product_id
LEFT JOIN inventory i ON p.product_id = i.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY total_revenue DESC;
```

### Inventory Turnover Analysis
```sql
SELECT p.product_name, p.category,
       AVG(i.stock_level) as avg_stock_level,
       SUM(s.quantity_sold) as total_sold,
       CASE 
         WHEN AVG(i.stock_level) > 0 THEN SUM(s.quantity_sold) / AVG(i.stock_level)
         ELSE 0 
       END as turnover_ratio
FROM products p
JOIN inventory i ON p.product_id = i.product_id
JOIN sales s ON p.product_id = s.product_id
WHERE s.sale_date >= '2024-01-01'
GROUP BY p.product_id, p.product_name, p.category
ORDER BY turnover_ratio DESC;
```

---

## Business Intelligence Use Cases

### Customer Analytics
- Customer segmentation by type and location
- Customer contact analysis and communication patterns
- Customer registration trends and growth analysis
- Geographic analysis of customer distribution
- Customer order behavior analysis

### Product Analytics
- Product performance and popularity analysis
- Category performance comparison
- Price analysis and optimization strategies
- Product sales trend analysis
- Inventory turnover analysis

### Sales Analytics
- Sales performance tracking and trend analysis
- Revenue analysis by period and product
- Sales volume analysis
- Price analysis and optimization
- Seasonal pattern identification

### Operational Analytics
- Order fulfillment performance analysis
- Inventory management and stock optimization
- Stock level monitoring and alerts
- Product availability analysis
- Sales and inventory correlation analysis

---

## Data Quality and Security

### Data Quality Rules
- All monetary amounts must be positive
- Date formats follow ISO standards
- Status values use predefined enumerations
- Foreign key relationships maintain referential integrity
- Email format validation for customers
- Unit price validation (unit_price > 0)
- Stock level validation (non-negative quantities)

### Security Considerations
- Personal data encryption for sensitive fields
- Access control and audit trails
- Data retention policies
- Customer data protection compliance
- Secure data transmission

---

## AI Integration Points

### SQL-Agent Capabilities
- Natural language to SQL query conversion
- Dynamic query generation based on business context
- Automated data exploration and pattern discovery
- Intelligent report generation and insights

### RAG Integration
- Business context retrieval for informed analysis
- Historical analysis and best practices access
- Domain-specific knowledge base integration
- Continuous learning and improvement

### Machine Learning Applications
- Demand forecasting and inventory optimization
- Customer segmentation and behavior prediction
- Price optimization and dynamic pricing
- Anomaly detection and fraud prevention
- Recommendation systems and personalization

This comprehensive schema provides the foundation for building an intelligent, AI-powered business analytics platform that can deliver actionable insights and automated decision support.
