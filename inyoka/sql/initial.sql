/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `__migration_info__`
--

DROP TABLE IF EXISTS `__migration_info__`;
CREATE TABLE `__migration_info__` (
  `schema_version` int(11) default NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

--
-- Dumping data for table `__migration_info__`
--

LOCK TABLES `__migration_info__` WRITE;
/*!40000 ALTER TABLE `__migration_info__` DISABLE KEYS */;
INSERT INTO `__migration_info__` VALUES (1);
/*!40000 ALTER TABLE `__migration_info__` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `forum_attachment`
--

DROP TABLE IF EXISTS `forum_attachment`;
CREATE TABLE `forum_attachment` (
  `id` int(11) NOT NULL auto_increment,
  `file` varchar(100) collate utf8_unicode_ci NOT NULL,
  `name` varchar(255) collate utf8_unicode_ci NOT NULL,
  `comment` longtext collate utf8_unicode_ci NOT NULL,
  `post_id` int(11) default NULL,
  PRIMARY KEY  (`id`),
  KEY `forum_attachment_post_id` (`post_id`),
  CONSTRAINT `post_id_refs_id_7ab9c308` FOREIGN KEY (`post_id`) REFERENCES `forum_post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `forum_forum`
--

DROP TABLE IF EXISTS `forum_forum`;
CREATE TABLE `forum_forum` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(100) collate utf8_unicode_ci NOT NULL,
  `slug` varchar(100) collate utf8_unicode_ci NOT NULL,
  `description` longtext collate utf8_unicode_ci NOT NULL,
  `parent_id` int(11) default NULL,
  `position` int(11) NOT NULL,
  `last_post_id` int(11) default NULL,
  `post_count` int(11) NOT NULL,
  `topic_count` int(11) NOT NULL,
  `welcome_message_id` int(11) default NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `slug` (`slug`),
  KEY `forum_forum_parent_id` (`parent_id`),
  KEY `forum_forum_last_post_id` (`last_post_id`),
  KEY `forum_forum_welcome_message_id` (`welcome_message_id`),
  CONSTRAINT `last_post_id_refs_id_54e78ec5` FOREIGN KEY (`last_post_id`) REFERENCES `forum_post` (`id`),
  CONSTRAINT `parent_id_refs_id_6d9fee7` FOREIGN KEY (`parent_id`) REFERENCES `forum_forum` (`id`),
  CONSTRAINT `welcome_message_id_refs_id_3914769c` FOREIGN KEY (`welcome_message_id`) REFERENCES `forum_welcomemessage` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `forum_poll`
--

DROP TABLE IF EXISTS `forum_poll`;
CREATE TABLE `forum_poll` (
  `id` int(11) NOT NULL auto_increment,
  `question` varchar(250) collate utf8_unicode_ci NOT NULL,
  `topic_id` int(11) default NULL,
  `start_time` datetime NOT NULL,
  `end_time` datetime default NULL,
  `multiple_votes` tinyint(1) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `forum_poll_topic_id` (`topic_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `forum_polloption`
--

DROP TABLE IF EXISTS `forum_polloption`;
CREATE TABLE `forum_polloption` (
  `id` int(11) NOT NULL auto_increment,
  `poll_id` int(11) NOT NULL,
  `name` varchar(250) collate utf8_unicode_ci NOT NULL,
  `votes` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `forum_polloption_poll_id` (`poll_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `forum_post`
--

DROP TABLE IF EXISTS `forum_post`;
CREATE TABLE `forum_post` (
  `id` int(11) NOT NULL auto_increment,
  `text` longtext collate utf8_unicode_ci NOT NULL,
  `rendered_text` longtext collate utf8_unicode_ci NOT NULL,
  `author_id` int(11) NOT NULL,
  `pub_date` datetime NOT NULL,
  `topic_id` int(11) NOT NULL,
  `hidden` tinyint(1) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `forum_post_author_id` (`author_id`),
  KEY `forum_post_topic_id` (`topic_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `forum_postrevision`
--

DROP TABLE IF EXISTS `forum_postrevision`;
CREATE TABLE `forum_postrevision` (
  `id` int(11) NOT NULL auto_increment,
  `post_id` int(11) NOT NULL,
  `text` longtext collate utf8_unicode_ci NOT NULL,
  `store_date` datetime NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `forum_postrevision_post_id` (`post_id`),
  CONSTRAINT `post_id_refs_id_3f5b50f4` FOREIGN KEY (`post_id`) REFERENCES `forum_post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `forum_privilege`
--

DROP TABLE IF EXISTS `forum_privilege`;
CREATE TABLE `forum_privilege` (
  `id` int(11) NOT NULL auto_increment,
  `group_id` int(11) default NULL,
  `user_id` int(11) default NULL,
  `forum_id` int(11) NOT NULL,
  `can_read` tinyint(1) NOT NULL,
  `can_reply` tinyint(1) NOT NULL,
  `can_create` tinyint(1) NOT NULL,
  `can_edit` tinyint(1) NOT NULL,
  `can_revert` tinyint(1) NOT NULL,
  `can_delete` tinyint(1) NOT NULL,
  `can_sticky` tinyint(1) NOT NULL,
  `can_vote` tinyint(1) NOT NULL,
  `can_create_poll` tinyint(1) NOT NULL,
  `can_upload` tinyint(1) NOT NULL,
  `can_moderate` tinyint(1) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `forum_privilege_group_id` (`group_id`),
  KEY `forum_privilege_user_id` (`user_id`),
  KEY `forum_privilege_forum_id` (`forum_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `forum_topic`
--

DROP TABLE IF EXISTS `forum_topic`;
CREATE TABLE `forum_topic` (
  `id` int(11) NOT NULL auto_increment,
  `forum_id` int(11) NOT NULL,
  `title` varchar(100) collate utf8_unicode_ci NOT NULL,
  `slug` varchar(50) collate utf8_unicode_ci default NULL,
  `view_count` int(11) NOT NULL,
  `post_count` int(11) NOT NULL,
  `sticky` tinyint(1) NOT NULL,
  `solved` tinyint(1) NOT NULL,
  `locked` tinyint(1) NOT NULL,
  `reported` longtext collate utf8_unicode_ci,
  `reporter_id` int(11) default NULL,
  `hidden` tinyint(1) NOT NULL,
  `ubuntu_version` varchar(5) collate utf8_unicode_ci default NULL,
  `ubuntu_distro` varchar(40) collate utf8_unicode_ci default NULL,
  `author_id` int(11) NOT NULL,
  `first_post_id` int(11) default NULL,
  `last_post_id` int(11) default NULL,
  `ikhaya_article_id` int(11) default NULL,
  `has_poll` tinyint(1) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `slug` (`slug`),
  KEY `forum_topic_forum_id` (`forum_id`),
  KEY `forum_topic_reporter_id` (`reporter_id`),
  KEY `forum_topic_author_id` (`author_id`),
  KEY `forum_topic_first_post_id` (`first_post_id`),
  KEY `forum_topic_last_post_id` (`last_post_id`),
  KEY `forum_topic_ikhaya_article_id` (`ikhaya_article_id`),
  CONSTRAINT `first_post_id_refs_id_7ced225d` FOREIGN KEY (`first_post_id`) REFERENCES `forum_post` (`id`),
  CONSTRAINT `ikhaya_article_id_refs_id_139c2301` FOREIGN KEY (`ikhaya_article_id`) REFERENCES `ikhaya_article` (`id`),
  CONSTRAINT `last_post_id_refs_id_7ced225d` FOREIGN KEY (`last_post_id`) REFERENCES `forum_post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `forum_voter`
--

DROP TABLE IF EXISTS `forum_voter`;
CREATE TABLE `forum_voter` (
  `id` int(11) NOT NULL auto_increment,
  `voter_id` int(11) NOT NULL,
  `poll_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `forum_voter_voter_id` (`voter_id`),
  KEY `forum_voter_poll_id` (`poll_id`),
  CONSTRAINT `poll_id_refs_id_c5ab617` FOREIGN KEY (`poll_id`) REFERENCES `forum_poll` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `forum_welcomemessage`
--

DROP TABLE IF EXISTS `forum_welcomemessage`;
CREATE TABLE `forum_welcomemessage` (
  `id` int(11) NOT NULL auto_increment,
  `title` varchar(120) collate utf8_unicode_ci NOT NULL,
  `text` longtext collate utf8_unicode_ci NOT NULL,
  `rendered_text` longtext collate utf8_unicode_ci NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `ikhaya_article`
--

DROP TABLE IF EXISTS `ikhaya_article`;
CREATE TABLE `ikhaya_article` (
  `id` int(11) NOT NULL auto_increment,
  `pub_date` datetime NOT NULL,
  `updated` datetime default NULL,
  `author_id` int(11) NOT NULL,
  `subject` varchar(180) collate utf8_unicode_ci NOT NULL,
  `category_id` int(11) NOT NULL,
  `icon_id` int(11) NOT NULL,
  `intro` longtext collate utf8_unicode_ci NOT NULL,
  `text` longtext collate utf8_unicode_ci NOT NULL,
  `public` tinyint(1) NOT NULL,
  `slug` varchar(100) collate utf8_unicode_ci NOT NULL,
  `is_xhtml` tinyint(1) NOT NULL,
  `comment_count` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `slug` (`slug`),
  KEY `ikhaya_article_author_id` (`author_id`),
  KEY `ikhaya_article_category_id` (`category_id`),
  KEY `ikhaya_article_icon_id` (`icon_id`),
  CONSTRAINT `icon_id_refs_id_5ba8ce87` FOREIGN KEY (`icon_id`) REFERENCES `ikhaya_icon` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `ikhaya_category`
--

DROP TABLE IF EXISTS `ikhaya_category`;
CREATE TABLE `ikhaya_category` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(180) collate utf8_unicode_ci NOT NULL,
  `slug` varchar(100) collate utf8_unicode_ci NOT NULL,
  `icon_id` int(11) default NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `slug` (`slug`),
  KEY `ikhaya_category_icon_id` (`icon_id`),
  CONSTRAINT `icon_id_refs_id_430f8ebc` FOREIGN KEY (`icon_id`) REFERENCES `ikhaya_icon` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `ikhaya_comment`
--

DROP TABLE IF EXISTS `ikhaya_comment`;
CREATE TABLE `ikhaya_comment` (
  `id` int(11) NOT NULL auto_increment,
  `article_id` int(11) default NULL,
  `title` varchar(100) collate utf8_unicode_ci NOT NULL,
  `text` longtext collate utf8_unicode_ci NOT NULL,
  `author_id` int(11) NOT NULL,
  `pub_date` datetime NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `ikhaya_comment_article_id` (`article_id`),
  KEY `ikhaya_comment_author_id` (`author_id`),
  CONSTRAINT `article_id_refs_id_4a281c46` FOREIGN KEY (`article_id`) REFERENCES `ikhaya_article` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `ikhaya_icon`
--

DROP TABLE IF EXISTS `ikhaya_icon`;
CREATE TABLE `ikhaya_icon` (
  `id` int(11) NOT NULL auto_increment,
  `identifier` varchar(100) collate utf8_unicode_ci NOT NULL,
  `img` varchar(100) collate utf8_unicode_ci NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `identifier` (`identifier`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `ikhaya_suggestion`
--

DROP TABLE IF EXISTS `ikhaya_suggestion`;
CREATE TABLE `ikhaya_suggestion` (
  `id` int(11) NOT NULL auto_increment,
  `author_id` int(11) NOT NULL,
  `pub_date` datetime NOT NULL,
  `title` varchar(100) collate utf8_unicode_ci NOT NULL,
  `text` longtext collate utf8_unicode_ci NOT NULL,
  `intro` longtext collate utf8_unicode_ci NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `ikhaya_suggestion_author_id` (`author_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `pastebin_entry`
--

DROP TABLE IF EXISTS `pastebin_entry`;
CREATE TABLE `pastebin_entry` (
  `id` int(11) NOT NULL auto_increment,
  `title` varchar(40) collate utf8_unicode_ci NOT NULL,
  `lang` varchar(20) collate utf8_unicode_ci NOT NULL,
  `code` longtext collate utf8_unicode_ci NOT NULL,
  `rendered_code` longtext collate utf8_unicode_ci NOT NULL,
  `pub_date` datetime NOT NULL,
  `author_id` int(11) NOT NULL,
  `referrer` longtext collate utf8_unicode_ci NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `pastebin_entry_author_id` (`author_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `planet_blog`
--

DROP TABLE IF EXISTS `planet_blog`;
CREATE TABLE `planet_blog` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(40) collate utf8_unicode_ci NOT NULL,
  `description` longtext collate utf8_unicode_ci,
  `blog_url` varchar(200) collate utf8_unicode_ci NOT NULL,
  `feed_url` varchar(200) collate utf8_unicode_ci NOT NULL,
  `icon` varchar(100) collate utf8_unicode_ci NOT NULL,
  `last_sync` datetime default NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `planet_entry`
--

DROP TABLE IF EXISTS `planet_entry`;
CREATE TABLE `planet_entry` (
  `id` int(11) NOT NULL auto_increment,
  `blog_id` int(11) NOT NULL,
  `guid` varchar(200) collate utf8_unicode_ci NOT NULL,
  `title` varchar(140) collate utf8_unicode_ci NOT NULL,
  `url` varchar(200) collate utf8_unicode_ci NOT NULL,
  `text` longtext collate utf8_unicode_ci NOT NULL,
  `pub_date` datetime NOT NULL,
  `updated` datetime NOT NULL,
  `author` varchar(50) collate utf8_unicode_ci NOT NULL,
  `author_homepage` varchar(200) collate utf8_unicode_ci default NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `guid` (`guid`),
  KEY `planet_entry_blog_id` (`blog_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `portal_event`
--

DROP TABLE IF EXISTS `portal_event`;
CREATE TABLE `portal_event` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(50) collate utf8_unicode_ci NOT NULL,
  `slug` varchar(50) collate utf8_unicode_ci NOT NULL,
  `changed` datetime NOT NULL,
  `created` datetime NOT NULL,
  `date` date NOT NULL,
  `time` time default NULL,
  `description` longtext collate utf8_unicode_ci NOT NULL,
  `author_id` int(11) NOT NULL,
  `location` varchar(50) collate utf8_unicode_ci NOT NULL,
  `location_town` varchar(20) collate utf8_unicode_ci NOT NULL,
  `location_lat` double default NULL,
  `location_long` double default NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `slug` (`slug`),
  UNIQUE KEY `portal_event_slug` (`slug`),
  KEY `portal_event_author_id` (`author_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `portal_group`
--

DROP TABLE IF EXISTS `portal_group`;
CREATE TABLE `portal_group` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(80) collate utf8_unicode_ci NOT NULL,
  `is_public` tinyint(1) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `portal_privatemessage`
--

DROP TABLE IF EXISTS `portal_privatemessage`;
CREATE TABLE `portal_privatemessage` (
  `id` int(11) NOT NULL auto_increment,
  `author_id` int(11) NOT NULL,
  `subject` varchar(255) collate utf8_unicode_ci NOT NULL,
  `pub_date` datetime NOT NULL,
  `text` longtext collate utf8_unicode_ci NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `portal_privatemessage_author_id` (`author_id`),
  CONSTRAINT `author_id_refs_id_77fbc3e4` FOREIGN KEY (`author_id`) REFERENCES `portal_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;


--
-- Table structure for table `portal_privatemessageentry`
--

DROP TABLE IF EXISTS `portal_privatemessageentry`;
CREATE TABLE `portal_privatemessageentry` (
  `id` int(11) NOT NULL auto_increment,
  `message_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `read` tinyint(1) NOT NULL,
  `folder` smallint(6) default NULL,
  `_order` int(11) default NULL,
  PRIMARY KEY  (`id`),
  KEY `portal_privatemessageentry_message_id` (`message_id`),
  KEY `portal_privatemessageentry_user_id` (`user_id`),
  CONSTRAINT `user_id_refs_id_713a6f0d` FOREIGN KEY (`user_id`) REFERENCES `portal_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `portal_searchqueue`
--

DROP TABLE IF EXISTS `portal_searchqueue`;
CREATE TABLE `portal_searchqueue` (
  `id` int(11) NOT NULL auto_increment,
  `component` varchar(1) collate utf8_unicode_ci NOT NULL,
  `doc_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `portal_sessioninfo`
--

DROP TABLE IF EXISTS `portal_sessioninfo`;
CREATE TABLE `portal_sessioninfo` (
  `id` int(11) NOT NULL auto_increment,
  `key` varchar(200) collate utf8_unicode_ci NOT NULL,
  `last_change` datetime NOT NULL,
  `subject_text` varchar(100) collate utf8_unicode_ci default NULL,
  `subject_type` varchar(20) collate utf8_unicode_ci NOT NULL,
  `subject_link` varchar(200) collate utf8_unicode_ci default NULL,
  `action` varchar(500) collate utf8_unicode_ci NOT NULL,
  `action_link` varchar(200) collate utf8_unicode_ci default NULL,
  `category` varchar(200) collate utf8_unicode_ci default NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `key` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `portal_staticpage`
--

DROP TABLE IF EXISTS `portal_staticpage`;
CREATE TABLE `portal_staticpage` (
  `key` varchar(25) collate utf8_unicode_ci NOT NULL,
  `title` varchar(200) collate utf8_unicode_ci NOT NULL,
  `content` longtext collate utf8_unicode_ci NOT NULL,
  PRIMARY KEY  (`key`),
  UNIQUE KEY `key` (`key`),
  UNIQUE KEY `portal_staticpage_key` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `portal_storage`
--

DROP TABLE IF EXISTS `portal_storage`;
CREATE TABLE `portal_storage` (
  `id` int(11) NOT NULL auto_increment,
  `key` varchar(200) collate utf8_unicode_ci NOT NULL,
  `value` longtext collate utf8_unicode_ci NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

LOCK TABLES `portal_storage` WRITE;
/*!40000 ALTER TABLE `portal_storage` DISABLE KEYS */;
INSERT INTO `portal_storage` VALUES (1,'markup_styles','');
/*!40000 ALTER TABLE `portal_storage` ENABLE KEYS */;
UNLOCK TABLES;


--
-- Table structure for table `portal_subscription`
--

DROP TABLE IF EXISTS `portal_subscription`;
CREATE TABLE `portal_subscription` (
  `id` int(11) NOT NULL auto_increment,
  `user_id` int(11) NOT NULL,
  `topic_id` int(11) default NULL,
  `wiki_page_id` int(11) default NULL,
  PRIMARY KEY  (`id`),
  KEY `portal_subscription_user_id` (`user_id`),
  KEY `portal_subscription_topic_id` (`topic_id`),
  KEY `portal_subscription_wiki_page_id` (`wiki_page_id`),
  CONSTRAINT `topic_id_refs_id_5d79c562` FOREIGN KEY (`topic_id`) REFERENCES `forum_topic` (`id`),
  CONSTRAINT `user_id_refs_id_23e8fe7b` FOREIGN KEY (`user_id`) REFERENCES `portal_user` (`id`),
  CONSTRAINT `wiki_page_id_refs_id_2aa7a96f` FOREIGN KEY (`wiki_page_id`) REFERENCES `wiki_page` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `portal_user`
--

DROP TABLE IF EXISTS `portal_user`;
CREATE TABLE `portal_user` (
  `id` int(11) NOT NULL auto_increment,
  `username` varchar(30) collate utf8_unicode_ci NOT NULL,
  `email` varchar(50) collate utf8_unicode_ci NOT NULL,
  `password` varchar(128) collate utf8_unicode_ci NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `last_login` datetime NOT NULL,
  `date_joined` datetime NOT NULL,
  `new_password_key` varchar(32) collate utf8_unicode_ci default NULL,
  `banned` datetime default NULL,
  `post_count` int(11) NOT NULL,
  `avatar` varchar(100) collate utf8_unicode_ci default NULL,
  `jabber` varchar(200) collate utf8_unicode_ci NOT NULL,
  `icq` varchar(16) collate utf8_unicode_ci NOT NULL,
  `msn` varchar(200) collate utf8_unicode_ci NOT NULL,
  `aim` varchar(200) collate utf8_unicode_ci NOT NULL,
  `yim` varchar(200) collate utf8_unicode_ci NOT NULL,
  `signature` longtext collate utf8_unicode_ci NOT NULL,
  `coordinates_long` double default NULL,
  `coordinates_lat` double default NULL,
  `location` varchar(200) collate utf8_unicode_ci NOT NULL,
  `gpgkey` varchar(8) collate utf8_unicode_ci NOT NULL,
  `occupation` varchar(200) collate utf8_unicode_ci NOT NULL,
  `interests` varchar(200) collate utf8_unicode_ci NOT NULL,
  `website` varchar(200) collate utf8_unicode_ci NOT NULL,
  `_settings` longtext collate utf8_unicode_ci NOT NULL,
  `is_manager` tinyint(1) NOT NULL,
  `forum_last_read` int(11) NOT NULL,
  `forum_read_status` longtext collate utf8_unicode_ci NOT NULL,
  `forum_welcome` longtext collate utf8_unicode_ci NOT NULL,
  `is_ikhaya_writer` tinyint(1) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

/*!40000 ALTER TABLE `portal_user` DISABLE KEYS */;
INSERT INTO `portal_user` VALUES (1,'anonymous','','!',0,NOW(),NOW(),NULL,NULL,0,NULL,'','','','','','',NULL,NULL,'','','','','','(dp1\n.',0,0,'','',0);
/*!40000 ALTER TABLE `portal_user` ENABLE KEYS */;
UNLOCK TABLES;


--
-- Table structure for table `portal_user_groups`
--

DROP TABLE IF EXISTS `portal_user_groups`;
CREATE TABLE `portal_user_groups` (
  `id` int(11) NOT NULL auto_increment,
  `user_id` int(11) NOT NULL,
  `group_id` int(11) NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `user_id` (`user_id`,`group_id`),
  KEY `group_id_refs_id_762ca89c` (`group_id`),
  CONSTRAINT `group_id_refs_id_762ca89c` FOREIGN KEY (`group_id`) REFERENCES `portal_group` (`id`),
  CONSTRAINT `user_id_refs_id_2676e679` FOREIGN KEY (`user_id`) REFERENCES `portal_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `portal_usererrorreport`
--

DROP TABLE IF EXISTS `portal_usererrorreport`;
CREATE TABLE `portal_usererrorreport` (
  `id` int(11) NOT NULL auto_increment,
  `title` varchar(50) collate utf8_unicode_ci NOT NULL,
  `text` longtext collate utf8_unicode_ci NOT NULL,
  `reporter_id` int(11) default NULL,
  `date` datetime NOT NULL,
  `url` varchar(200) collate utf8_unicode_ci NOT NULL,
  `assigned_to_id` int(11) default NULL,
  `done` tinyint(1) NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `portal_usererrorreport_reporter_id` (`reporter_id`),
  KEY `portal_usererrorreport_assigned_to_id` (`assigned_to_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `wiki_attachment`
--

DROP TABLE IF EXISTS `wiki_attachment`;
CREATE TABLE `wiki_attachment` (
  `id` int(11) NOT NULL auto_increment,
  `file` varchar(100) collate utf8_unicode_ci NOT NULL,
  PRIMARY KEY  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `wiki_metadata`
--

DROP TABLE IF EXISTS `wiki_metadata`;
CREATE TABLE `wiki_metadata` (
  `id` int(11) NOT NULL auto_increment,
  `page_id` int(11) NOT NULL,
  `key` varchar(30) collate utf8_unicode_ci NOT NULL,
  `value` varchar(512) collate utf8_unicode_ci NOT NULL,
  PRIMARY KEY  (`id`),
  KEY `wiki_metadata_page_id` (`page_id`),
  CONSTRAINT `page_id_refs_id_373882bf` FOREIGN KEY (`page_id`) REFERENCES `wiki_page` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `wiki_page`
--

DROP TABLE IF EXISTS `wiki_page`;
CREATE TABLE `wiki_page` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(200) collate utf8_unicode_ci NOT NULL,
  `topic_id` int(11) default NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `wiki_page_topic_id` (`topic_id`),
  CONSTRAINT `topic_id_refs_id_3c888ab8` FOREIGN KEY (`topic_id`) REFERENCES `forum_topic` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `wiki_revision`
--

DROP TABLE IF EXISTS `wiki_revision`;
CREATE TABLE `wiki_revision` (
  `id` int(11) NOT NULL auto_increment,
  `page_id` int(11) NOT NULL,
  `text_id` int(11) NOT NULL,
  `user_id` int(11) default NULL,
  `change_date` datetime NOT NULL,
  `note` varchar(512) collate utf8_unicode_ci NOT NULL,
  `deleted` tinyint(1) NOT NULL,
  `remote_addr` varchar(200) collate utf8_unicode_ci default NULL,
  `attachment_id` int(11) default NULL,
  PRIMARY KEY  (`id`),
  KEY `wiki_revision_page_id` (`page_id`),
  KEY `wiki_revision_text_id` (`text_id`),
  KEY `wiki_revision_user_id` (`user_id`),
  KEY `wiki_revision_attachment_id` (`attachment_id`),
  CONSTRAINT `attachment_id_refs_id_5c4351ed` FOREIGN KEY (`attachment_id`) REFERENCES `wiki_attachment` (`id`),
  CONSTRAINT `page_id_refs_id_d7553bf` FOREIGN KEY (`page_id`) REFERENCES `wiki_page` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Table structure for table `wiki_text`
--

DROP TABLE IF EXISTS `wiki_text`;
CREATE TABLE `wiki_text` (
  `id` int(11) NOT NULL auto_increment,
  `value` longtext collate utf8_unicode_ci NOT NULL,
  `hash` varchar(40) collate utf8_unicode_ci NOT NULL,
  PRIMARY KEY  (`id`),
  UNIQUE KEY `hash` (`hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
