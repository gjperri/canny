const express = require('express');
const cors = require('cors');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { Pool } = require('pg');

const app = express();
const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://localhost/canny'
});

app.use(cors());
app.use(express.json());

const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-in-production';

// Middleware to verify JWT token
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  
  if (!token) return res.status(401).json({ error: 'Access denied' });
  
  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) return res.status(403).json({ error: 'Invalid token' });
    req.user = user;
    next();
  });
};

// AUTH ROUTES
app.post('/api/auth/register', async (req, res) => {
  try {
    const { email, password, full_name, current_role } = req.body;
    const password_hash = await bcrypt.hash(password, 10);
    
    const result = await pool.query(
      'INSERT INTO users (email, password_hash, full_name, "current_role") VALUES ($1, $2, $3, $4) RETURNING id, email, full_name, "current_role"',
      [email, password_hash, full_name, current_role]
    );
    
    const token = jwt.sign({ userId: result.rows[0].id }, JWT_SECRET);
    res.json({ token, user: result.rows[0] });
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    const result = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
    
    if (result.rows.length === 0) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    const user = result.rows[0];
    const validPassword = await bcrypt.compare(password, user.password_hash);
    
    if (!validPassword) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    const token = jwt.sign({ userId: user.id }, JWT_SECRET);
    res.json({ 
      token, 
      user: { 
        id: user.id, 
        email: user.email, 
        full_name: user.full_name,
        current_role: user.current_role 
      } 
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// USER ROUTES
app.get('/api/users/:id', async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT id, full_name, "current_role", bio, created_at FROM users WHERE id = $1',
      [req.params.id]
    );
    
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.put('/api/users/profile', authenticateToken, async (req, res) => {
  try {
    const { full_name, current_role, bio } = req.body;
    const result = await pool.query(
      'UPDATE users SET full_name = $1, "current_role" = $2, bio = $3 WHERE id = $4 RETURNING id, full_name, "current_role", bio',
      [full_name, current_role, bio, req.user.userId]
    );
    
    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// LEARNING ITEMS ROUTES
app.post('/api/learning-items', authenticateToken, async (req, res) => {
  try {
    const { title, type, author, status, notes } = req.body;
    const result = await pool.query(
      'INSERT INTO learning_items (user_id, title, type, author, status, notes) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *',
      [req.user.userId, title, type, author, status, notes]
    );
    
    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/users/:id/learning-items', async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT * FROM learning_items WHERE user_id = $1 AND is_public = true ORDER BY started_at DESC',
      [req.params.id]
    );
    
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.put('/api/learning-items/:id', authenticateToken, async (req, res) => {
  try {
    const { title, type, author, status, notes } = req.body;
    const result = await pool.query(
      'UPDATE learning_items SET title = $1, type = $2, author = $3, status = $4, notes = $5 WHERE id = $6 AND user_id = $7 RETURNING *',
      [title, type, author, status, notes, req.params.id, req.user.userId]
    );
    
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Learning item not found' });
    }
    
    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.delete('/api/learning-items/:id', authenticateToken, async (req, res) => {
  try {
    await pool.query(
      'DELETE FROM learning_items WHERE id = $1 AND user_id = $2',
      [req.params.id, req.user.userId]
    );
    
    res.json({ message: 'Deleted successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// FOLLOW ROUTES
app.post('/api/follows/:userId', authenticateToken, async (req, res) => {
  try {
    const result = await pool.query(
      'INSERT INTO follows (follower_id, following_id) VALUES ($1, $2) RETURNING *',
      [req.user.userId, req.params.userId]
    );
    
    res.json(result.rows[0]);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

app.delete('/api/follows/:userId', authenticateToken, async (req, res) => {
  try {
    await pool.query(
      'DELETE FROM follows WHERE follower_id = $1 AND following_id = $2',
      [req.user.userId, req.params.userId]
    );
    
    res.json({ message: 'Unfollowed successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/feed', authenticateToken, async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT li.*, u.full_name, u.current_role 
      FROM learning_items li
      JOIN users u ON li.user_id = u.id
      WHERE li.user_id IN (
        SELECT following_id FROM follows WHERE follower_id = $1
      ) AND li.is_public = true
      ORDER BY li.started_at DESC
      LIMIT 50
    `, [req.user.userId]);
    
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});