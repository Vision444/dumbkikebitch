import discord
import asyncio
import logging
from typing import Dict, Any, Optional, List
import re

logger = logging.getLogger(__name__)


class PasswordCommandHandler:
    def __init__(self, bot, db_manager, encryption_manager):
        self.bot = bot
        self.db_manager = db_manager
        self.encryption_manager = encryption_manager
        self.user_states = {}  # State machine storage
        self.timeout_duration = 120  # 120 seconds timeout

    async def handle_message(self, message):
        """Handle incoming messages and route to appropriate command handlers"""
        content = message.content.strip()

        # Check if user is in a state flow
        if message.author.id in self.user_states:
            await self.handle_state_response(message)
            return

        # Parse command
        if content.startswith("!"):
            parts = content[1:].split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            # Route to appropriate command
            if command == "new":
                await self.handle_new_command(message, args)
            elif command == "get":
                await self.handle_get_command(message, args)
            elif command == "list":
                await self.handle_list_command(message)
            elif command == "delete":
                await self.handle_delete_command(message, args)
            elif command == "update":
                await self.handle_update_command(message, args)
            elif command == "help":
                await self.handle_help_command(message)

    async def handle_new_command(self, message, args):
        """Handle !new command - both single and multi-step paths"""
        user_id = message.author.id

        if args:
            # Quick path: service name provided
            service_name = args.strip()
            await self.start_password_creation(message, service_name)
        else:
            # Multi-step path: ask for service name first
            await message.author.send(
                "🔐 **Password Creation**\n\nEnter the service name (e.g., Gmail, Netflix):"
            )
            self.user_states[user_id] = {
                "state": "awaiting_service",
                "action": "create",
            }

    async def start_password_creation(self, message, service_name):
        """Start the password creation process for a given service"""
        user_id = message.author.id

        # Check for existing entry
        existing = await self.db_manager.get_password(user_id, service_name)
        if existing:
            await message.author.send(
                f"⚠️ A password for '{service_name}' already exists. Use `!update {service_name}` to modify it."
            )
            return

        # Store service name and ask for username
        self.user_states[user_id] = {
            "state": "awaiting_username",
            "action": "create",
            "service_name": service_name,
        }

        await message.author.send(
            f"Enter username for {service_name} (or type 'skip' for no username):"
        )

    async def handle_get_command(self, message, args):
        """Handle !get command"""
        if not args:
            await message.author.send("❌ Usage: `!get <service_name>`")
            return

        service_name = args.strip()
        user_id = message.author.id

        password_entry = await self.db_manager.get_password(user_id, service_name)

        if not password_entry:
            await message.author.send(f"❌ No password found for '{service_name}'")
            return

        try:
            decrypted_password = self.encryption_manager.decrypt(
                password_entry["encrypted_payload"]
            )

            embed = discord.Embed(
                title=f"🔑 {password_entry['service_name']}",
                color=discord.Color.green(),
            )

            if password_entry["username"]:
                embed.add_field(
                    name="Username",
                    value=f"``{password_entry['username']}``",
                    inline=False,
                )

            embed.add_field(
                name="Password", value=f"||{decrypted_password}||", inline=False
            )
            embed.add_field(
                name="Created",
                value=password_entry["created_at"].strftime("%Y-%m-%d %H:%M"),
                inline=True,
            )
            embed.add_field(
                name="Updated",
                value=password_entry["updated_at"].strftime("%Y-%m-%d %H:%M"),
                inline=True,
            )

            msg = await message.author.send(embed=embed)

            # Auto-delete after 60 seconds for security
            await asyncio.sleep(60)
            try:
                await msg.delete()
            except:
                pass

        except Exception as e:
            logger.error(f"Error decrypting password: {e}")
            await message.author.send("❌ Error retrieving password")

    async def handle_list_command(self, message):
        """Handle !list command"""
        user_id = message.author.id
        passwords = await self.db_manager.list_passwords(user_id)

        if not passwords:
            await message.author.send(
                "📋 No passwords stored yet. Use `!new` to add one."
            )
            return

        embed = discord.Embed(
            title="📋 Stored Passwords",
            description=f"You have {len(passwords)} password(s) stored",
            color=discord.Color.blue(),
        )

        for password in passwords:
            username_text = f" ({password['username']})" if password["username"] else ""
            embed.add_field(
                name=password["service_name"],
                value=f"Username: {password['username'] or 'N/A'}{username_text}\nUpdated: {password['updated_at'].strftime('%Y-%m-%d')}",
                inline=False,
            )

        await message.author.send(embed=embed)

    async def handle_delete_command(self, message, args):
        """Handle !delete command"""
        if not args:
            await message.author.send("❌ Usage: `!delete <service_name>`")
            return

        service_name = args.strip()
        user_id = message.author.id

        # Check if password exists
        existing = await self.db_manager.get_password(user_id, service_name)
        if not existing:
            await message.author.send(f"❌ No password found for '{service_name}'")
            return

        # Ask for confirmation
        self.user_states[user_id] = {
            "state": "awaiting_delete_confirmation",
            "service_name": service_name,
        }

        embed = discord.Embed(
            title="🗑️ Delete Confirmation",
            description=f"Are you sure you want to delete the password for '{service_name}'?",
            color=discord.Color.red(),
        )

        msg = await message.author.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

    async def handle_update_command(self, message, args):
        """Handle !update command"""
        if not args:
            await message.author.send("❌ Usage: `!update <service_name>`")
            return

        service_name = args.strip()
        user_id = message.author.id

        # Check if password exists
        existing = await self.db_manager.get_password(user_id, service_name)
        if not existing:
            await message.author.send(
                f"❌ No password found for '{service_name}'. Use `!new {service_name}` to create it."
            )
            return

        # Start update process
        self.user_states[user_id] = {
            "state": "awaiting_new_username",
            "action": "update",
            "service_name": service_name,
        }

        await message.author.send(
            f"📝 **Update {service_name}**\n\nEnter new username (or type 'skip' to keep current):"
        )

    async def handle_help_command(self, message):
        """Handle !help command"""
        embed = discord.Embed(
            title="🔐 Password Manager Help",
            description="Secure password management commands",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Commands",
            value="`!new [service]` - Create new password\n"
            "`!get <service>` - Retrieve password\n"
            "`!list` - List all services\n"
            "`!update <service>` - Update password\n"
            "`!delete <service>` - Delete password\n"
            "`!help` - Show this help",
            inline=False,
        )

        embed.add_field(
            name="Security Features",
            value="• All passwords encrypted with Fernet\n"
            "• Credentials sent via DM only\n"
            "• Auto-deletion of password messages\n"
            "• 120-second timeout for operations",
            inline=False,
        )

        await message.author.send(embed=embed)

    async def handle_state_response(self, message):
        """Handle responses in multi-step command flows"""
        user_id = message.author.id
        content = message.content.strip()

        if user_id not in self.user_states:
            return

        state_info = self.user_states[user_id]
        state = state_info["state"]

        try:
            if state == "awaiting_service":
                service_name = content
                if service_name.lower() == "cancel":
                    await message.author.send("❌ Password creation cancelled.")
                    del self.user_states[user_id]
                    return
                await self.start_password_creation(message, service_name)

            elif state == "awaiting_username":
                username = content if content.lower() != "skip" else None
                state_info["username"] = username
                state_info["state"] = "awaiting_password"
                await message.author.send("Enter the password:")

            elif state == "awaiting_password":
                password = content
                if password.lower() == "cancel":
                    await message.author.send("❌ Password creation cancelled.")
                    del self.user_states[user_id]
                    return

                await self.finalize_password_creation(message, password)

            elif state == "awaiting_new_username":
                username = content if content.lower() != "skip" else None
                state_info["username"] = username
                state_info["state"] = "awaiting_new_password"
                await message.author.send("Enter the new password:")

            elif state == "awaiting_new_password":
                password = content
                if password.lower() == "cancel":
                    await message.author.send("❌ Password update cancelled.")
                    del self.user_states[user_id]
                    return

                await self.finalize_password_update(message, password)

            elif state == "awaiting_delete_confirmation":
                # This is handled by reaction events
                pass

        except Exception as e:
            logger.error(f"Error in state response: {e}")
            await message.author.send("❌ An error occurred. Please try again.")
            if user_id in self.user_states:
                del self.user_states[user_id]

    async def finalize_password_creation(self, message, password):
        """Finalize password creation"""
        user_id = message.author.id
        state_info = self.user_states[user_id]

        try:
            encrypted_password = self.encryption_manager.encrypt(password)

            await self.db_manager.create_password(
                user_id,
                state_info["service_name"],
                state_info["username"] or "",
                encrypted_password,
            )

            await message.author.send(
                f"✅ Password for '{state_info['service_name']}' created successfully!"
            )
            del self.user_states[user_id]

        except Exception as e:
            logger.error(f"Error creating password: {e}")
            await message.author.send("❌ Failed to create password. Please try again.")

    async def finalize_password_update(self, message, password):
        """Finalize password update"""
        user_id = message.author.id
        state_info = self.user_states[user_id]

        try:
            encrypted_password = self.encryption_manager.encrypt(password)

            success = await self.db_manager.update_password(
                user_id,
                state_info["service_name"],
                state_info["username"] or "",
                encrypted_password,
            )

            if success:
                await message.author.send(
                    f"✅ Password for '{state_info['service_name']}' updated successfully!"
                )
            else:
                await message.author.send("❌ Failed to update password.")

            del self.user_states[user_id]

        except Exception as e:
            logger.error(f"Error updating password: {e}")
            await message.author.send("❌ Failed to update password. Please try again.")

    async def handle_reaction(self, payload):
        """Handle reaction events for confirmations"""
        user_id = payload.user_id
        if user_id not in self.user_states:
            return

        state_info = self.user_states[user_id]

        if state_info["state"] == "awaiting_delete_confirmation":
            if str(payload.emoji) == "✅":
                # Confirm deletion
                try:
                    success = await self.db_manager.delete_password(
                        user_id, state_info["service_name"]
                    )
                    if success:
                        await self.bot.get_user(user_id).send(
                            f"✅ Password for '{state_info['service_name']}' deleted successfully!"
                        )
                    else:
                        await self.bot.get_user(user_id).send(
                            "❌ Failed to delete password."
                        )
                except Exception as e:
                    logger.error(f"Error deleting password: {e}")
                    await self.bot.get_user(user_id).send(
                        "❌ Failed to delete password."
                    )

                del self.user_states[user_id]

            elif str(payload.emoji) == "❌":
                # Cancel deletion
                await self.bot.get_user(user_id).send("❌ Password deletion cancelled.")
                del self.user_states[user_id]

    async def cleanup_expired_states(self):
        """Clean up expired user states"""
        current_time = asyncio.get_event_loop().time()
        expired_users = []

        for user_id, state_info in self.user_states.items():
            if current_time - state_info.get("created_at", 0) > self.timeout_duration:
                expired_users.append(user_id)

        for user_id in expired_users:
            try:
                await self.bot.get_user(user_id).send(
                    "⏱️ Session expired. Please start over."
                )
            except:
                pass
            del self.user_states[user_id]
