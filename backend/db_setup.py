
import psycopg2
from psycopg2 import sql

# Database Configuration (Default local Docker settings)
DB_HOST = "localhost"
DB_NAME = "db"
DB_USER = "user"
DB_PASS = "password"
DB_PORT = "5432"

def setup_database():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        cur = conn.cursor()

        # Create users table
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            firebase_uid VARCHAR(128) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        # Create user_preferences table
        create_preferences_table = """
        CREATE TABLE IF NOT EXISTS user_preferences (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            category VARCHAR(100) NOT NULL,
            preference_data JSONB NOT NULL,
            source VARCHAR(50) DEFAULT 'onboarding',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        # Create knowledge table (parent/container for materials)
        create_knowledge_table = """
        CREATE TABLE IF NOT EXISTS knowledge (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        # Create materials table (children of knowledge)
        create_materials_table = """
        CREATE TABLE IF NOT EXISTS materials (
            id SERIAL PRIMARY KEY,
            knowledge_id INTEGER NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            original_filename VARCHAR(255) NOT NULL,
            storage_path VARCHAR(500) NOT NULL,
            storage_bucket VARCHAR(100) NOT NULL,
            file_size BIGINT,
            mime_type VARCHAR(100) DEFAULT 'application/pdf',
            status VARCHAR(50) DEFAULT 'pending',
            pdf_metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        # Create assessments table
        create_assessments_table = """
        CREATE TABLE IF NOT EXISTS assessments (
            id SERIAL PRIMARY KEY,
            material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(50) DEFAULT 'not_started',
            score INTEGER,
            total_questions INTEGER DEFAULT 10,
            summary TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            assessment_type VARCHAR(20) DEFAULT 'pre',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        # Create questions table
        create_questions_table = """
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            question_text TEXT NOT NULL,
            options JSONB NOT NULL,
            correct_answer VARCHAR(10) NOT NULL,
            explanation TEXT,
            difficulty VARCHAR(20),
            order_number INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT valid_order CHECK (order_number BETWEEN 1 AND 10)
        );
        """

        # Create user_answers table
        create_user_answers_table = """
        CREATE TABLE IF NOT EXISTS user_answers (
            id SERIAL PRIMARY KEY,
            assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            user_answer VARCHAR(10) NOT NULL,
            is_correct BOOLEAN NOT NULL,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(assessment_id, question_id)
        );
        """

        # Create indexes
        create_indexes = """
        CREATE INDEX IF NOT EXISTS idx_firebase_uid ON users(firebase_uid);
        CREATE INDEX IF NOT EXISTS idx_user_prefs ON user_preferences(user_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_category_lookup ON user_preferences(user_id, category, is_active);
        CREATE INDEX IF NOT EXISTS idx_jsonb_data ON user_preferences USING GIN(preference_data);
        CREATE INDEX IF NOT EXISTS idx_created_at ON user_preferences(created_at DESC);
        """

        # Create indexes for knowledge
        create_knowledge_indexes = """
        CREATE INDEX IF NOT EXISTS idx_knowledge_user ON knowledge(user_id);
        CREATE INDEX IF NOT EXISTS idx_knowledge_name ON knowledge(name);
        CREATE INDEX IF NOT EXISTS idx_knowledge_created ON knowledge(created_at DESC);
        """

        # Create indexes for materials
        create_materials_indexes = """
        CREATE INDEX IF NOT EXISTS idx_materials_knowledge ON materials(knowledge_id);
        CREATE INDEX IF NOT EXISTS idx_materials_user ON materials(user_id);
        CREATE INDEX IF NOT EXISTS idx_materials_status ON materials(status);
        CREATE INDEX IF NOT EXISTS idx_materials_storage ON materials(storage_bucket, storage_path);
        CREATE INDEX IF NOT EXISTS idx_materials_metadata ON materials USING GIN(pdf_metadata);
        """

        # Create indexes for assessments
        create_assessments_indexes = """
        CREATE INDEX IF NOT EXISTS idx_assessments_material ON assessments(material_id);
        CREATE INDEX IF NOT EXISTS idx_assessments_user ON assessments(user_id);
        CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
        CREATE INDEX IF NOT EXISTS idx_assessments_type ON assessments(assessment_type);
        CREATE INDEX IF NOT EXISTS idx_assessments_completed ON assessments(completed_at DESC);
        """

        # Create indexes for questions
        create_questions_indexes = """
        CREATE INDEX IF NOT EXISTS idx_questions_material ON questions(material_id);
        CREATE INDEX IF NOT EXISTS idx_questions_order ON questions(material_id, order_number);
        """

        # Create indexes for user_answers
        create_answers_indexes = """
        CREATE INDEX IF NOT EXISTS idx_answers_assessment ON user_answers(assessment_id);
        CREATE INDEX IF NOT EXISTS idx_answers_question ON user_answers(question_id);
        CREATE INDEX IF NOT EXISTS idx_answers_correct ON user_answers(is_correct);
        """

        cur.execute(create_users_table)
        cur.execute(create_preferences_table)
        cur.execute(create_knowledge_table)
        cur.execute(create_materials_table)
        cur.execute(create_assessments_table)
        
        # Migration: Add assessment_type if it doesn't exist
        cur.execute("ALTER TABLE assessments ADD COLUMN IF NOT EXISTS assessment_type VARCHAR(20) DEFAULT 'pre';")

        cur.execute(create_questions_table)
        cur.execute(create_user_answers_table)
        cur.execute(create_indexes)
        cur.execute(create_knowledge_indexes)
        cur.execute(create_materials_indexes)
        cur.execute(create_assessments_indexes)
        cur.execute(create_questions_indexes)
        cur.execute(create_answers_indexes)

        conn.commit()

        print("✅ Database schema created successfully")
        print("   - users table (with firebase_uid)")
        print("   - user_preferences table")
        print("   - knowledge table")
        print("   - materials table")
        print("   - assessments table")
        print("   - questions table")
        print("   - user_answers table")
        print("   - all indexes created")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error setting up database: {e}")

if __name__ == "__main__":
    setup_database()
